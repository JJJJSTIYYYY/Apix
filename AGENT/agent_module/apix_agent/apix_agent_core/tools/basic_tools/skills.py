import asyncio
import io
from pathlib import Path
from typing import Annotated
import zipfile

import httpx
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.global_config import FILE_SERVICE_URL
from apix_agent.apix_agent_core.tools.prompt import LOAD_SKILL_PROMPT


@tool(description=LOAD_SKILL_PROMPT)
async def load_skill(
    name: str | list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    
    if isinstance(name, str):
        skill_names = [name]
    else:
        skill_names = name

    client_id = state.get("client_id")
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "load_skill",
            "tool_call_id": tool_call_id,
            "content": str(skill_names),
            "chunk_position": "start",
            "status": "success",
        }
    )

    config = state.get("config", {})
    container_id = state.get("sandbox")
    base_path = config.get("work_dir")

    if not container_id:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "load_skill",
                "tool_call_id": tool_call_id,
                "content": "Error: Sandbox not configured.",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please info the user to configure it.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    if not base_path:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "load_skill",
                "tool_call_id": tool_call_id,
                "content": "Error: Sandbox not configured.",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: No work_dir configured by user. Please info the user to configure it.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    skills = state.get("skills") or []

    name_to_id = {
        s["skill_name"]: s["skill_id"]
        for s in skills
    }

    invalid = [n for n in skill_names if n not in name_to_id]
    if invalid:
        skill_names_available = list(name_to_id.keys())

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "load_skill",
                "tool_call_id": tool_call_id,
                "content": f"Error: Skill: {invalid} is not available.",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    f"Error: Skill: {invalid} is not available.\nAvailable skills: {skill_names_available}",
                    tool_call_id=tool_call_id
                )
            ]
        })

    skill_dir = Path(base_path) / "SKILL"
    skill_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(5)

    async def load_one(name: str):

        skill_id = name_to_id[name]

        skill_root = skill_dir / name
        skill_md_path = skill_root / "SKILL.md"

        try:
            if not skill_md_path.exists():

                async with semaphore:

                    url = f"{FILE_SERVICE_URL}/file/skills/fetch_skill"

                    async with httpx.AsyncClient(timeout=120) as client:
                        resp = await client.get(
                            url,
                            params={
                                "skill_id": skill_id,
                                "client_id": client_id
                            }
                        )

                    if resp.status_code != 200:
                        raise RuntimeError(
                            f"Failed to download skill package: {resp.text}"
                        )

                    zip_bytes = resp.content

                    def extract():
                        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                            zf.extractall(skill_dir)

                    await asyncio.to_thread(extract)

            if not skill_md_path.exists():
                skill_md_path = next(skill_root.rglob("SKILL.md"))

            guide = skill_md_path.read_text(encoding="utf-8")

            if guide.startswith("---"):
                parts = guide.split("---", 2)
                if len(parts) >= 3:
                    guide = parts[2].lstrip("\n")

            return {
                "status": "ok",
                "name": name,
                "guide": guide
            }

        except Exception as e:
            return {
                "status": "error",
                "name": name,
                "error": f"{type(e)}: {str(e)}"
            }

    results = await asyncio.gather(
        *(load_one(n) for n in skill_names),
        return_exceptions=False
    )

    loaded_skills_cache = state.get("loaded_skills_cache", []) or []

    success = []
    failed = []

    for r in results:
        if r["status"] == "ok":
            success.append(r["name"])
            loaded_skills_cache.append((
                r["name"],
                False,
                r["guide"] + f"\n\n## Skill Relevant Files in Directory `/workspace/SKILL/{r['name']}`"
            ))
        else:
            failed.append(f"{r['name']}: {r['error']}")

    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_END, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "load_skill",
            "tool_call_id": tool_call_id,
            "content": f"{len(success)} success, {len(failed)} failed",
            "chunk_position": "end",
            "status": "success" if success else "fail",
        }
    )

    msg = ""
    if success:
        msg += f"Loaded skills: {success}\n"
    if failed:
        msg += "\nFailed:\n" + "\n".join(failed)

    return Command(update={
        "messages": [
            ToolMessage(msg.strip(), tool_call_id=tool_call_id)
        ],
        "loaded_skills_cache": loaded_skills_cache
    })