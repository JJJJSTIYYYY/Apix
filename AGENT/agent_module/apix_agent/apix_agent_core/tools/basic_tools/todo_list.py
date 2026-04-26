from typing import Annotated
from pathlib import Path
import hashlib

from langchain.agents.middleware.todo import WRITE_TODOS_TOOL_DESCRIPTION, Todo
from langchain.messages import ToolMessage
from langchain.tools import InjectedState, tool, InjectedToolCallId
from langgraph.types import Command

from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.commons.file_content_reader import load_from_yaml, update_to_yaml
from apix_agent.global_config import BASE_DIR


WRITE_MEMO_TOOL_DESCRIPTION = """
Use this tool to record your important decisions, observations, conclusions or other important information during the current work session.
This tool helps you record previous information so that you can review them later if you forget.
## When to Use This Tool
Use this tool in these scenarios:
1. When you are making an important decision
2. When defining constraints, rules, or policies that must be remembered
3. When you make a tool call, the summary or conclusion of the call result that must be remembered
4. When summarizing a important conclusion or observations that must be remembered
5. When you observe that a memo in your memorandum is outdated and should be deleted (Use a same title and empty content for delete)
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
"""

READ_MEMO_TOOL_DESCRIPTION = """
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
"""


@tool(description=WRITE_TODOS_TOOL_DESCRIPTION)
async def write_todos(
    todos: list[Todo], 
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Create and manage a structured task list for your current work session."""
    client_id = state.get("client_id")
    target_platform = state.get("platform")

    event_writer = AgentStreamWriter()
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target_id=client_id, 
        target_platform=target_platform,
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
        target_id=client_id, 
        target_platform=target_platform,
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
async def update_memorandum(
    title: str,
    content: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Write / Overwrite or delete a memorandum.

    Args:
        title (str): Memorandum title (must not be empty)
        content (str): Memorandum content (empty means delete)
    """
    client_id = state.get("client_id")
    target_platform = state.get("platform")

    event_writer = AgentStreamWriter()

    # Start event
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START,
        target_id=client_id,
        target_platform=target_platform,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "update_memorandum",
            "tool_call_id": tool_call_id,
            "content": "Update memorandum",
            "chunk_position": "start",
            "status": "success",
        }
    )

    # Title must not be empty (content CAN be empty -> delete)
    if not title.strip():
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target_id=client_id,
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memorandum",
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
            target_id=client_id,
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memorandum",
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

    # Build file path
    memo_dir = Path(BASE_DIR) / "memo"
    memo_dir.mkdir(parents=True, exist_ok=True)

    hash_input = f"{client_id}:{history_id}".encode("utf-8")
    memo_filename = hashlib.sha256(hash_input).hexdigest()
    memo_path = memo_dir / f"{memo_filename}.yaml"

    try:
        # Detect previous existence (for action type)
        previous_titles = set(state.get("memorandum") or [])
        existed_before = title in previous_titles

        # Update YAML
        updated_data = update_to_yaml(memo_path, title, content)

        # Always rebuild from YAML (single source of truth)
        current_memos = list(updated_data.keys())

        # Determine action
        if not content.strip():
            action = "deleted"
        elif existed_before:
            action = "updated"
        else:
            action = "created"

        # End event
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target_id=client_id,
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memorandum",
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
                        f"Memorandum {action} successfully. \n\n* Current memo titles in your memorandum: {current_memos}.",
                        tool_call_id=tool_call_id,
                    )
                ],
                "memorandum": current_memos,
            }
        )

    except Exception as e:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END,
            target_id=client_id,
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_memorandum",
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
                        f"Failed to update memorandum: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
    
    
@tool(description=READ_MEMO_TOOL_DESCRIPTION)
async def read_memorandum(
    title: list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Read one or more memorandum(s) content before making a important decision.

    Args:
        title (list[str]): Titles of memoranda in the `Current Memorandum Title List` to read.
    """
    client_id = state.get("client_id")
    target_platform = state.get("platform")

    event_writer = AgentStreamWriter()
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target_id=client_id, 
        target_platform=target_platform,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "read_memorandum",
            "tool_call_id": tool_call_id,
            "content": "Read memorandum",
            "chunk_position": "start",
            "status": "success",
        }
    )

    history_id = state.get("history_id")
    if not client_id or not history_id:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_memorandum",
                "tool_call_id": tool_call_id,
                "content": "Error occurred",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        return Command(
            update={
                "messages": [
                    ToolMessage("[SYSTEM LEVEL] Error: Essential key not found in state.", tool_call_id=tool_call_id)
                ]
            }
        )

    memo_dir = Path(BASE_DIR) / "memo"
    hash_input = f"{client_id}:{history_id}".encode("utf-8")
    memo_filename = hashlib.sha256(hash_input).hexdigest()
    memo_path = memo_dir / f"{memo_filename}.yaml"

    if not memo_path.exists():
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_memorandum",
                "tool_call_id": tool_call_id,
                "content": "Nothing here",
                "chunk_position": "end",
                "status": "success",
            }
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "No memorandum has been written yet in this session.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    try:
        contents = []
        if not title:
            content = str(load_from_yaml(memo_path)) # Load all if no specific title provided
            contents.append(content.strip() if content else "No content found.")
        if isinstance(title, str):
            title = [title]
        for t in title:
            content = str(load_from_yaml(memo_path, t))
            contents.append(content.strip() if content else f"No content found for title: {t}.")

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_memorandum",
                "tool_call_id": tool_call_id,
                "content": f"Read {" ".join(title)}",
                "chunk_position": "end",
                "status": "success",
            }
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "\n".join(contents),
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    except Exception as e:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_memorandum",
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