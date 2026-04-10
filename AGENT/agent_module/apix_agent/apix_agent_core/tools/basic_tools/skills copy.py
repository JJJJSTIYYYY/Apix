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
from langgraph.config import get_stream_writer

from apix_agent.global_config import FILE_SERVICE_URL


@tool
async def load_skill(
    name: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Load the guide for a skill.
    The sandbox must be configured before use this tool.

    Skills provide reusable capabilities that help you accomplish tasks.
    Each skill contains documentation (SKILL.md) that explains:
    - how to use it
    - what commands or tools it provides
    - usage examples

    When this tool is called, the skill package will be downloaded and
    extracted into the sandbox at:

        /workspace/SKILL/{skill_name}

    You should read the SKILL.md file in that directory at first to understand
    how to use the skill.

    ## When to Use This Tool
    Use this tool in these scenarios:
    - the user's task clearly requires the capability provided by that skill
    - you need more detailed instructions to proceed
    ## When NOT to Use This Tool
    Do NOT use this tool when:
    - skill package has already exists in workspace.
    - you do not need a skill to compelete current task.
    ## Important Guidelines
    Avoid loading skills unnecessarily, as this may waste time and resources.

    Args:
        name (str): The name of the skill to load.

    Returns:
        str: The skill guide (SKILL.md content) if successful, or an error message if loading fails.
    """

    writer = get_stream_writer()

    writer({"tool_chunk_rtn": {
        "tool_call_id": tool_call_id,
        "tool_chunk_rtn": "load_skill",
        "content": name,
        "chunk_position": "start",
        "status": "success",
    }})

    config = state.get("config", {})
    container_id = state.get("sandbox")
    base_path = config.get("work_dir")

    if not container_id:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "load_skill",
            "content": "Error: Sandbox not configured.",
            "chunk_position": "end",
            "status": "fail",
        }})
        
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please call configure_sandbox first.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    if not base_path:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "load_skill",
            "content": "Error: Sandbox not configured.",
            "chunk_position": "end",
            "status": "fail",
        }})
        
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: No work_dir configured by user.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    skills = state.get("skills") or []
    skill_id = None
    for skill in skills:
        if skill['skill_name'] == name:
            skill_id = skill['skill_id']

    if not skill_id:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "load_skill",
            "content": f"Error: Skill: {name} is not available.",
            "chunk_position": "end",
            "status": "fail",
        }})
        
        skill_names = [item['skill_name'] for item in skills]
        return Command(update={
            "messages": [
                ToolMessage(
                    f"Error: Skill: {name} is not available.\nAvailable skills: {str(skill_names)}",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:

        skill_dir = Path(base_path) / "SKILL"
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md_path = skill_dir / name / "SKILL.md"

        if not skill_md_path.exists():

            client_id = state["client_id"]

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

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                await asyncio.to_thread(zf.extractall, skill_dir)

        if not skill_md_path.exists():
            raise RuntimeError("SKILL.md not found in skill package.")

        guide = skill_md_path.read_text(encoding="utf-8")

        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "load_skill",
            "content": f"Skill '{name}' loaded.",
            "chunk_position": "end",
            "status": "success",
        }})
        content = f"""{guide}

---

## Skill Relevant Files Saved to /workspace/SKILL/{name}
"""

        return Command(update={
            "messages": [
                ToolMessage(
                    content,
                    tool_call_id=tool_call_id
                )
            ]
        })

    except Exception as e:

        err = f"Error loading skill '{name}': {str(e)}"

        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "load_skill",
            "content": err,
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(update={
            "messages": [
                ToolMessage(
                    err,
                    tool_call_id=tool_call_id
                )
            ]
        })
