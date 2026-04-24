from typing import Annotated
from pathlib import Path
import hashlib

from langchain.agents.middleware.todo import WRITE_TODOS_TOOL_DESCRIPTION, Todo
from langchain.messages import ToolMessage
from langchain.tools import InjectedState, tool, InjectedToolCallId
from langgraph.types import Command

from apix_agent.apix_event_pipe.stream_writer import ApixStreamWriter, StreamEvent
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.commons.file_content_reader import load_from_yaml, append_to_yaml
from apix_agent.global_config import BASE_DIR


WRITE_MEMO_TOOL_DESCRIPTION = """
Use this tool to record important decisions, conclusions, assumptions, or strategic reasoning that should persist during the current work session.
This tool is NOT for task tracking or step management. Use the todo tool for organizing actions.
## When to Use This Tool
Use this tool in these scenarios:
1. After making an important design or architectural decision
2. When defining constraints, rules, or policies that must be remembered
3. When identifying key assumptions that affect future reasoning
4. When summarizing a strategic conclusion that should not be forgotten
5. When you want to externalize reasoning that may influence future steps
## When NOT to Use This Tool
Do NOT use this tool when:
1. You are listing tasks or tracking progress (use the todo tool instead)
2. The information is trivial or short-lived
3. The reasoning is obvious and unlikely to impact future decisions
4. The task can be completed immediately without future implications
5. You are simply answering a question
## Important Guidelines
- Record only high-value, decision-level information.
- Be concise but precise.
- Do not restate the entire conversation.
- Focus on what must be remembered for correct future behavior.
- Avoid duplicating todo content.
This tool is for decision memory, not action management.
"""

READ_MEMO_TOOL_DESCRIPTION = """
Use this tool to retrieve previously recorded strategic decisions, assumptions, or constraints for the current work session.
This tool helps you maintain reasoning consistency across steps.
## When to Use This Tool
Use this tool in these scenarios:
1. When you need to remember the user's request, determine the real objective
2. Before making a new design or architectural decision
3. When you need to check previously defined constraints or policies
4. If you suspect earlier decisions may affect your current reasoning
5. When resuming work after multiple steps and you want to ensure alignment
6. Before modifying an existing plan that may have prior assumptions
## When NOT to Use This Tool
Do NOT use this tool when:
1. You are looking for task progress (use the todo tool instead)
2. The task is trivial and unlikely to depend on prior decisions
3. You have just written the memo and already remember its content
4. You are simply answering a question that does not depend on past decisions
5. You are trying to retrieve general conversation history
## Important Guidelines
- Use this tool proactively when reasoning consistency matters.
- Avoid unnecessary repeated reads.
- Only consult it when prior strategic decisions may influence correctness.
- Treat retrieved content as high-priority reasoning context.
This tool restores decision memory, not task state or full conversation history.
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

    event_writer = ApixStreamWriter()
    event_writer.send_event(
        event=StreamEvent.TOOL_EXEC_START, 
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
        event=StreamEvent.TOOL_EXEC_END, 
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
async def write_memorandum(
    title: str,
    content: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Write or Overwrite a memorandum after important decisions, conclusions,
    assumptions, or strategic reasoning that should persist during
    the current work session.

    Args:
        title (str): The title of the memorandum, should be concise and indicative of the content.
        content (str): The detailed content of the memorandum, recording the important information to be remembered.
    """
    client_id = state.get("client_id")
    target_platform = state.get("platform")

    event_writer = ApixStreamWriter()
    event_writer.send_event(
        event=StreamEvent.TOOL_EXEC_START, 
        target_id=client_id, 
        target_platform=target_platform,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "write_memorandum",
            "tool_call_id": tool_call_id,
            "content": "Update memorandum",
            "chunk_position": "start",
            "status": "success",
        }
    )

    if not content.strip() or not title.strip():
        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_memorandum",
                "tool_call_id": tool_call_id,
                "content": "Empty title or content",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Error: Title and content cannot be empty.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    history_id = state.get("history_id")
    if not client_id or not history_id:
        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_memorandum",
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
                        tool_call_id=tool_call_id
                    )
                ]
            }
        )

    memo_dir = Path(BASE_DIR) / "memo"
    memo_dir.mkdir(parents=True, exist_ok=True)

    hash_input = f"{client_id}:{history_id}".encode("utf-8")
    memo_filename = hashlib.sha256(hash_input).hexdigest()
    memo_path = memo_dir / f"{memo_filename}.yaml"


    try:
        append_to_yaml(memo_path, {title: content})
        current_memos = state.get("memorandum", []) + [title]

        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_memorandum",
                "tool_call_id": tool_call_id,
                "content": "Finish",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Memorandum appended successfully. Current memo titles: {current_memos}.",
                        tool_call_id=tool_call_id,
                    )
                ],
                "memorandum": current_memos,
            }
        )

    except Exception as e:
        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_memorandum",
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
                        f"Failed to write memorandum: {str(e)}",
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

    event_writer = ApixStreamWriter()
    event_writer.send_event(
        event=StreamEvent.TOOL_EXEC_START, 
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
            event=StreamEvent.TOOL_EXEC_END, 
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
            event=StreamEvent.TOOL_EXEC_END, 
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
            event=StreamEvent.TOOL_EXEC_END, 
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
            event=StreamEvent.TOOL_EXEC_END, 
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