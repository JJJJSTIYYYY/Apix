from datetime import datetime
from typing import Annotated, Literal, Optional
from pathlib import Path
import hashlib

from langchain.agents.middleware.todo import WRITE_TODOS_TOOL_DESCRIPTION, Todo
from langchain.messages import ToolMessage
from langchain.tools import InjectedState, tool, InjectedToolCallId
from langgraph.types import Command
import yaml

from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.commons.file_content_reader import load_from_yaml
from apix_agent.global_config import BASE_DIR
from apix_agent.commons.logger import logger


WRITE_MEMO_TOOL_DESCRIPTION = """
## Write / Overwrite or delete a memory:
Use this tool to record your important decisions, observations, conclusions or other important information during the current work session.
This tool helps you record previous information so that you can review them later if you forget.
## When to Use This Tool
Use this tool in these scenarios:
1. When you are making an important decision
2. When defining constraints, rules, or policies that must be remembered
3. When you make a tool call, the summary or conclusion of the call result that must be remembered
4. When summarizing a important conclusion or observations that must be remembered
5. When you observe that a memo in your memory is outdated and should be deleted (Use a same title and empty content for delete)
## When NOT to Use This Tool
Do NOT use this tool when:
1. You are listing tasks or tracking progress (use the todo tool instead)
2. You haven't yet reached any valuable or strategic information
3. You are simply answering a question
## Important Guidelines
- Record only high-value, decision-level, conclusion-related information.
- Do not restate the entire conversation.
- Focus on what must be remembered for correct future behavior.
- Avoid duplicating todo content.
## Args:
    title (str): Memory title (must not be empty)
    content (str): Memory content (empty means delete)
"""

READ_MEMO_TOOL_DESCRIPTION = """
## Read one or more memory(s) content:
Use this tool to retrieve previously recorded strategic decisions, observations, conclusions or other information for the current work session.
This tool helps you recall important past information and maintain consistency.
## When to Use This Tool
Use this tool in these scenarios:
1. Before making a decision that may conflict with previously recorded conclusions
2. When you need to verify existing constraints, rules, or policies
3. When a choice depends on previously established observations or conclusions
4. When you suspect a similar decision has already been made and should not be re-derived
5. When correctness depends on aligning with prior decisions or tool result summaries
## When NOT to Use This Tool
Do NOT use this tool when:
1. The current step is independent and does not rely on prior decisions
2. You are simply answering a question that does not depend on past decisions
3. You have just written the memo and already remember its content
4. You are trying to retrieve general conversation history
## Important Guidelines
- Do not use it as a substitute for conversation history or planning context.
- Avoid unnecessary reads, only use it when prior information affect correctness.
## Args:
    title (list[str]): Titles of memories in the `## Available Memories` section to be read.
"""


def update_to_yaml(
    file_path: Path,
    title: str,
    content: str,
    date: str,
    source: Literal["conversation", "workspace"],
) -> list[dict]:
    """
    Update or delete memo in yaml file.

    Args:
        file_path (Path): yaml file path
        title (str): memo title
        content (str): memo content, if empty -> delete
        date (str): memo date, e.g. 2025-06-07
        source (Literal["conversation", "workspace"]): memo source

    Returns:
        list[dict]: latest full memo list
    """
    try:
        content = content or ""
        # Load existing data
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
        else:
            data = []

        if not isinstance(data, list):
            logger.warning(
                f"[update_to_yaml] Invalid yaml structure in {file_path}, resetting to empty list."
            )
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

        logger.info("[update_to_yaml] yaml updated successfully.")

        return data

    except Exception as e:
        logger.error(f"[update_to_yaml] Error: {e}")
        raise


@tool(description=WRITE_TODOS_TOOL_DESCRIPTION)
async def write_todos(
    todos: list[Todo], 
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Create and manage a structured task list for your current work session."""
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



@tool(description=WRITE_MEMO_TOOL_DESCRIPTION)
async def update_memory(
    title: str,
    content: Optional[str] = "",
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
            "content": "Update memory",
            "chunk_position": "start",
            "status": "success",
        }
    )

    content = content or ""

    # Title must not be empty (content CAN be empty -> delete)
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
        memo_source = "workspace" if workspace else "conversation"

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

    # Delete must clear both namespaces to avoid stale override resurrection
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

    try:
        existed_before = existing_memo is not None

        # Update target yaml(s)
        for path in target_paths:
            update_to_yaml(
                file_path=path,
                title=title,
                content=content,
                date=datetime.now().strftime("%Y-%m-%d"),
                source=memo_source,
            )

        # Reload merged memorandum
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

        merged_memorandum = list(merged_map.values())

        if not content.strip():
            action = "deleted"
        elif existed_before:
            action = "updated"
        else:
            action = "created"

        current_memo_titles = [
            memo["title"]
            for memo in merged_memorandum
            if memo.get("title")
        ]
        
        merged_memorandum = sorted(
            merged_map.values(),
            key=lambda x: x.get("date", ""),
            reverse=True,
        )

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memory",
                "tool_call_id": tool_call_id,
                "content": action,
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Memory {action} successfully. "
                        f"\n\n* Current memorandum titles: {current_memo_titles}.",
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
                        f"Failed to update memory: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )


@tool(description=READ_MEMO_TOOL_DESCRIPTION)
async def read_memory(
    title: Optional[list[str]],
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