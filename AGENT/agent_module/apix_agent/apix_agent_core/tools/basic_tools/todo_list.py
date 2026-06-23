from datetime import datetime
from typing import Annotated, Literal, Optional, TypedDict
from pathlib import Path
import hashlib

from langchain.agents.middleware.todo import WRITE_TODOS_TOOL_DESCRIPTION, Todo
from langchain.messages import ToolMessage
from langchain.tools import InjectedState, tool, InjectedToolCallId
from langgraph.types import Command
import yaml

from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.commons.file_content_reader import load_from_yaml
from apix_agent.global_config import BASE_DIR
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.tools.prompt import READ_MEMORY_PROMPT, UPDATE_MEMORY_PROMPT, WRITE_TODOS_PROMPT

def update_memory_to_yaml(
    file_path: Path,
    title: str,
    abstract: str | None,
    content: str,
    date: str,
    source: Literal["conversation", "workspace"],
) -> list[dict]:
    """
    Update or delete memo in yaml file.

    Args:
        file_path (Path): yaml file path
        title (str): memo title
        abstract (str | None): brief summary of the memory
        content (str): memo content, if empty -> delete
        date (str): memo date, e.g. 2025-06-07
        source (Literal["conversation", "workspace"]): memo source

    Returns:
        list[dict]: latest full memo list
    """
    try:
        content = content or ""

        # Normalize abstract
        abstract = (
            abstract.strip()
            if isinstance(abstract, str)
            else None
        )

        if not abstract:
            abstract = None

        # Load existing data
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
        else:
            data = []

        if not isinstance(data, list):
            logger.warning(f"Invalid yaml structure in {file_path}, resetting to empty list.")
            data = []

        # Remove all same-title memos first
        data = [
            memo
            for memo in data
            if memo.get("title") != title
        ]

        # Re-insert latest version if content not empty
        if content.strip():
            data.append({
                "title": title,
                "abstract": abstract,
                "date": date,
                "content": content,
                "source": source,
            })

        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                data,
                f,
                allow_unicode=True,
                sort_keys=False,
            )

        logger.info("Yaml updated successfully.")

        return data

    except Exception as e:
        logger.error(f"Error: {e}")
        raise


@tool(description=WRITE_TODOS_PROMPT)
async def write_todos(
    todos: list[Todo], 
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "write_todos",
            "tool_call_id": tool_call_id,
            "content": todos,
            "chunk_position": "start",
            "status": "success",
        }
    )
    
    if not state.get("task_id", None):
        addtional_info = {"todo_list": todos}
        await ai_context_manager.append_info_message(
            state.get("generation_id"), 
            state.get("client_id"), 
            state.get("history_id"), 
            state.get("timestamp"),
            addtional_info,
            state.get("parent_node_id")
        )

    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_END, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "write_todos",
            "tool_call_id": tool_call_id,
            "content": f"Finish",
            "chunk_position": "end",
            "status": "success",
        }
    )
    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(f"Updated todo list to {todos}", tool_call_id=tool_call_id)
            ],
        }
    )


class Memory(TypedDict):
    title: str
    abstract: Optional[str]
    content: Optional[str]


@tool(description=UPDATE_MEMORY_PROMPT)
async def update_memory(
    memories: list[Memory],
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:

    client_id = state.get("client_id")
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)

    # Start event
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START,
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "update_memory",
            "tool_call_id": tool_call_id,
            "content": "Update memories",
            "chunk_position": "start",
            "status": "success",
        }
    )

    if not memories:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Error: memories cannot be empty.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    # Validate all titles first
    for memory in memories:
        title = memory.get("title", "")

        if not title.strip():
            event_writer.send_event(
                event=AgentStreamEvent.TOOL_EXEC_END,
                target=target,
                data={
                    "event_name": "tool_exec_chunk_rtn",
                    "tool_name": "update_memory",
                    "tool_call_id": tool_call_id,
                    "content": "Empty title",
                    "chunk_position": "end",
                    "status": "fail",
                }
            )

            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            "Error: Title cannot be empty.",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

    history_id = state.get("history_id")

    if not client_id or not history_id:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memory",
                "tool_call_id": tool_call_id,
                "content": "Missing state keys",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "[SYSTEM LEVEL] Error: Essential key not found in state.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    workspace = state.get("config", {}).get("work_dir")

    memo_namespace = (
        client_id
        + ":"
        + (workspace or history_id)
        + ":"
        + state.get("agent_role")
    )

    fallback_memo_namespace = (
        client_id
        + ":"
        + history_id
        + ":"
        + state.get("agent_role")
    )

    memo_dir = Path(BASE_DIR) / "memo"
    memo_dir.mkdir(parents=True, exist_ok=True)

    workspace_hash = hashlib.sha256(
        memo_namespace.encode("utf-8")
    ).hexdigest()

    workspace_path = memo_dir / f"{workspace_hash}.yaml"

    fallback_hash = hashlib.sha256(
        fallback_memo_namespace.encode("utf-8")
    ).hexdigest()

    fallback_path = memo_dir / f"{fallback_hash}.yaml"

    try:
        actions: list[str] = []

        for memory in memories:

            title = memory["title"]
            abstract = memory.get("abstract")
            content = memory.get("content") or ""

            # Delete operation should not keep abstract
            if not content.strip():
                abstract = None

            existing_memo = next(
                (
                    memo
                    for memo in (state.get("memorandum") or [])
                    if memo.get("title") == title
                ),
                None,
            )

            # Existing memo keeps its original source namespace
            if existing_memo:
                memo_source = existing_memo.get("source") or (
                    "workspace" if workspace else "conversation"
                )
            else:
                memo_source = (
                    "workspace"
                    if workspace
                    else "conversation"
                )

            # Delete must clear both namespaces
            if not content.strip():
                target_paths = {
                    workspace_path,
                    fallback_path,
                }

            else:
                target_path = (
                    workspace_path
                    if memo_source == "workspace"
                    else fallback_path
                )

                target_paths = {target_path}

            existed_before = existing_memo is not None

            for path in target_paths:
                update_memory_to_yaml(
                    file_path=path,
                    title=title,
                    abstract=abstract,
                    content=content,
                    date=datetime.now().strftime("%Y-%m-%d"),
                    source=memo_source,
                )

            if not content.strip():
                action = "deleted"
            elif existed_before:
                action = "updated"
            else:
                action = "created"

            actions.append(f"{title}: {action}")

        # Reload merged memorandum once
        merged_map = {}

        for path in [fallback_path, workspace_path]:

            if not path.exists():
                continue

            data = load_from_yaml(path) or []

            if not isinstance(data, list):
                continue

            for memo in data:

                memo_title = memo.get("title")

                if not memo_title:
                    continue

                existing = merged_map.get(memo_title)

                # Keep latest memo by date
                if (
                    not existing
                    or memo.get("date", "")
                    > existing.get("date", "")
                ):
                    merged_map[memo_title] = memo

        merged_memorandum = sorted(
            merged_map.values(),
            key=lambda x: x.get("date", ""),
            reverse=True,
        )

        current_memo_titles = [
            memo["title"]
            for memo in merged_memorandum
            if memo.get("title")
        ]

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memory",
                "tool_call_id": tool_call_id,
                "content": "Batch update success",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Memory operations completed:"
                        f"\n- " + "\n- ".join(actions)
                        + f"\n\n* Current available memory: {current_memo_titles}.",
                        tool_call_id=tool_call_id,
                    )
                ],
                "memorandum": merged_memorandum,
            }
        )

    except Exception as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memory",
                "tool_call_id": tool_call_id,
                "content": f"Error occurred {str(e)}",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Failed to update memories: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )


@tool(description=READ_MEMORY_PROMPT)
async def read_memory(
    title: Optional[str | list[str]],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:

    client_id = state.get("client_id")
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)

    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START,
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "read_memory",
            "tool_call_id": tool_call_id,
            "content": "Read memory",
            "chunk_position": "start",
            "status": "success",
        }
    )

    history_id = state.get("history_id")

    if not client_id or not history_id:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_memory",
                "tool_call_id": tool_call_id,
                "content": "Error occurred",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "[SYSTEM LEVEL] Error: Essential key not found in state.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    try:
        memorandum_list = state.get("memorandum") or []

        if isinstance(title, str):
            title = [title]

        contents = []

        if not title:
            event_writer.send_event(
                event=AgentStreamEvent.TOOL_EXEC_END,
                target=target,
                data={
                    "event_name": "tool_exec_chunk_rtn",
                    "tool_name": "read_memory",
                    "tool_call_id": tool_call_id,
                    "content": "No title provided.",
                    "chunk_position": "end",
                    "status": "fail",
                }
            )

            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            "A title is required.",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        memorandum_map = {
            memo.get("title"): memo
            for memo in memorandum_list
            if memo.get("title")
        }

        for t in title:
            memo = memorandum_map.get(t)

            if not memo:
                contents.append(f"No content found for title: {t}.")
                continue

            contents.append(
                f"Title: {memo.get('title', '')}\n"
                f"Date: {memo.get('date', '')}\n"
                f"Content:\n{memo.get('content', '')}"
            )

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_memory",
                "tool_call_id": tool_call_id,
                "content": f"Read {' '.join(title)}",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "\n\n---\n\n".join(contents) if contents else "No memory found.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    except Exception as e:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_memory",
                "tool_call_id": tool_call_id,
                "content": f"Error occurred {str(e)}",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Failed to read memo: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )