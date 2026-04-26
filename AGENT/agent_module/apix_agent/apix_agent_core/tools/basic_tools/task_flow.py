from typing import Annotated, TypedDict, Literal

import httpx
from langchain.messages import ToolMessage
from langchain.tools import InjectedState, tool, InjectedToolCallId
from langgraph.types import Command

from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.global_config import TASK_SERVER_BASE_URL




class TestTask(TypedDict, total=False):
    id: str
    task_id: str
    client_id: str
    mock: str
    name: str
    type: str
    address: str
    script: str
    description: str
    status: Literal["pending", "running", "finished"]
    result: str


@tool
async def get_test_task(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Use this tool to fetch one executable test task from the task manager server.
    The fetched task will automatically be moved from "pending" to "running" state on the server side.

    This tool is the ENTRY POINT for executing automated test tasks. You should call this tool when you are ready to start working on a new test case.

    ## When to Use This Tool
    Use this tool in these scenarios:

    1. When you need a new test task to execute
    2. When there is no current task in progress (state.current_test_task is empty)
    3. After finishing a previous task and reporting the result
    4. When the user asks you to run or process test tasks

    ## How to Use This Tool
    1. Call this tool to retrieve a single task from the queue
    2. The returned task will contain:
       - id: unique case ID (used later for updating result)
       - type: task type (interface / database / script)
       - address / script: execution target
       - description: expected validation logic
       - mock: mock data or context
    3. Store and use the returned task from state.current_test_task
    4. Execute the task according to its type and description
    5. After execution, you MUST call `update_test_task` to report the result

    ## Important Behavior
    - This call will BLOCK if no pending task is available (server-side queue behavior)
    - Each call only returns ONE task
    - The task is immediately marked as "running" once fetched
    - You are responsible for finishing it (no auto-timeout or rollback)

    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. You already have a task in progress (state.current_test_task is not empty)
    2. You have not yet reported the result of the previous task
    3. You are only reasoning or planning without executing tasks

    ## Execution Responsibility
    Once you fetch a task:
    - You MUST attempt to execute it
    - You MUST call update_test_task after execution
    - Never abandon a running task without reporting result

    ## Best Practice
    - Always follow this pattern:
      1. get_test_task → 2. execute → 3. update_test_task
    - Do NOT fetch multiple tasks in parallel unless explicitly required
    - Treat each task as atomic and independent
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
            "tool_name": "get_task",
            "tool_call_id": tool_call_id,
            "content": "fetching task from task server",
            "chunk_position": "start",
            "status": "success",
        }
    )

    payload = {
        "client_id": client_id
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{TASK_SERVER_BASE_URL}/plugin/get_task",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        err_msg = f"[ERROR] get_task failed: {str(exc)}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "get_task",
                "tool_call_id": tool_call_id,
                "content": err_msg,
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(content=err_msg, tool_call_id=tool_call_id)
                ]
            }
        )

    if not data.get("success"):
        err_msg = f"[ERROR] get_task returned failure: {data.get('messages')}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "get_task",
                "tool_call_id": tool_call_id,
                "content": err_msg,
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(content=err_msg, tool_call_id=tool_call_id)
                ]
            }
        )

    task: TestTask = data.get("messages", {}).get("task") or {}
    pending_task = data.get("messages", {}).get("pending_task", 0)
    running_task = data.get("messages", {}).get("running_task", 0)
    finished_task = data.get("messages", {}).get("finished_task", 0)

    case_id = task.get("id", "")
    case_name = (task.get("name", "") or "").strip()
    case_type = (task.get("type", "") or "").strip().lower()
    address = (task.get("address", "") or "").strip()
    script = task.get("script", "") or ""
    description = (task.get("description", "") or "").strip()
    mock = (task.get("mock", "") or "").strip()

    if case_type == "interface":
        success_msg = (
            "# Interface Test Task\n\n"
            f"- **Case ID**: `{case_id}`\n"
            f"- **Case Name**: {case_name or 'N/A'}\n"
            f"- **Case Type**: Interface Test\n"
            f"- **Interface URL**: `{address or 'N/A'}`\n"
            f"- **Description**: {description or 'N/A'}\n"
            f"- **Mock Data**: {mock or 'N/A'}\n\n"
            "# Task Progress\n\n"
            f"- **Pending**: {pending_task}"
            f"- **In_progress**: {running_task}"
            f"- **Compeleted**: {finished_task}"
        )
    elif case_type == "database":
        success_msg = (
            "# Database Operation Task\n\n"
            f"- **Case ID**: `{case_id}`\n"
            f"- **Case Name**: {case_name or 'N/A'}\n"
            f"- **Case Type**: Database Operation\n"
            f"- **Database Address**: `{address or 'N/A'}`\n"
            f"- **Description**: {description or 'N/A'}\n"
            f"- **Mock Data**: {mock or 'N/A'}\n\n"
            "# Task Progress\n\n"
            f"- **Pending**: {pending_task}"
            f"- **In_progress**: {running_task}"
            f"- **Compeleted**: {finished_task}"
        )
    elif case_type == "script":
        success_msg = (
            "# Script Execution Task\n\n"
            f"- **Case ID**: `{case_id}`\n"
            f"- **Case Name**: {case_name or 'N/A'}\n"
            f"- **Case Type**: Script Execution\n"
            f"- **Script Content**:\n"
            f"```text\n{script}\n```\n"
            f"- **Description**: {description or 'N/A'}\n"
            f"- **Mock Data**: {mock or 'N/A'}\n\n"
            "# Task Progress\n\n"
            f"- **Pending**: {pending_task}"
            f"- **In_progress**: {running_task}"
            f"- **Compeleted**: {finished_task}"
        )
    else:
        success_msg = (
            "# Generic Test Task\n\n"
            f"- **Case ID**: `{case_id}`\n"
            f"- **Case Name**: {case_name or 'N/A'}\n"
            f"- **Case Type**: {case_type or 'unknown'}\n"
            f"- **Raw Address**: `{address or 'N/A'}`\n"
            f"- **Raw Script**:\n"
            f"```text\n{script}\n```\n"
            f"- **Description**: {description or 'N/A'}\n"
            f"- **Mock Data**: {mock or 'N/A'}\n\n"
            "# Task Progress\n\n"
            f"- **Pending**: {pending_task}"
            f"- **In_progress**: {running_task}"
            f"- **Compeleted**: {finished_task}"
        )

    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_END, 
        target_id=client_id, 
        target_platform=target_platform,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "get_task",
            "tool_call_id": tool_call_id,
            "content": f"Get task {case_name}",
            "chunk_position": "end",
            "status": "success",
        }
    )

    return Command(
        update={
            "current_test_task": task,
            "current_test_case_id": case_id,
            "messages": [
                ToolMessage(content=success_msg, tool_call_id=tool_call_id)
            ],
        }
    )


@tool
async def update_test_task(
    result: str,
    case_id: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Use this tool to report the execution result of a running test task and mark it as "finished" on the task manager server.

    This tool FINALIZES a test task. Every task fetched via `get_test_task` MUST eventually be completed using this tool.

    ## When to Use This Tool
    Use this tool in these scenarios:

    1. After successfully executing a test task
    2. After a test execution fails and you need to report the failure
    3. When you have a clear result (success / failure / error / partial)
    4. When state.current_test_case_id exists

    ## How to Use This Tool
    1. Prepare a clear and concise result string:
       - Include execution outcome
       - Include key validation points
       - Include error messages if any
    2. Call this tool with:
       - result: execution result description
       - case_id (optional): if not provided, it will use state.current_test_case_id
    3. The task will be transitioned from "running" to "finished"
    4. The state will be updated and the current task will be cleared

    ## Result Writing Guidelines
    Your result should be:
    - Clear and structured
    - Focused on verification outcome
    - Contain important signals, such as:
      - status code
      - response correctness
      - validation checks
      - errors or exceptions

    Examples:
    - "Test passed: HTTP 200, expected fields returned, data validated."
    - "Test failed: API returned HTTP 500."
    - "Test error: request timed out."

    ## Important Constraints
    - Only "running" tasks can be updated
    - Status must be "finished" (enforced by server)
    - Each task can ONLY be updated ONCE

    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. You have not executed the task yet
    2. There is no current task (state.current_test_case_id is empty)
    3. You are unsure about the result
    4. You are still in the middle of execution

    ## Execution Responsibility
    - You MUST call this tool after every get_test_task
    - Never leave a task in "running" state indefinitely
    - If execution fails, still report the failure result

    ## Best Practice
    - Always follow this lifecycle:
      get_test_task → execute → update_test_task
    - Do NOT skip result reporting
    - Do NOT fabricate results — be accurate and explicit
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
            "tool_name": "update_task",
            "tool_call_id": tool_call_id,
            "content": "Updating task result",
            "chunk_position": "start",
            "status": "success",
        }
    )

    if not case_id:
        err_msg = "update_test_task failed: no case_id was provided and state.current_test_case_id is missing."

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_task",
                "tool_call_id": tool_call_id,
                "content": err_msg,
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(content=err_msg, tool_call_id=tool_call_id)
                ]
            }
        )

    payload = {
        "id": case_id,
        "result": result,
        "status": "finished",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{TASK_SERVER_BASE_URL}/plugin/update_task",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        err_msg = f"[ERROR] update_task failed: {str(exc)}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_task",
                "tool_call_id": tool_call_id,
                "content": err_msg,
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(content=err_msg, tool_call_id=tool_call_id)
                ]
            }
        )

    if not data.get("success"):
        err_msg = f"[ERROR] update_task returned failure: {data.get('messages')}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "update_task",
                "tool_call_id": tool_call_id,
                "content": err_msg,
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(content=err_msg, tool_call_id=tool_call_id)
                ]
            }
        )

    updated_task: TestTask = data.get("messages", {}) or {}

    success_msg = (
        "# Test Task Updated\n\n"
        f"- **Case ID**: `{updated_task.get('id', '')}`\n"
        f"- **Task Status**: {updated_task.get('status', 'N/A')}\n"
        f"- **Execution Result**: {updated_task.get('result', 'N/A')}\n"
    )

    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_END, 
        target_id=client_id, 
        target_platform=target_platform,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "update_task",
            "tool_call_id": tool_call_id,
            "content": "Updated",
            "chunk_position": "end",
            "status": "success",
        }
    )

    return Command(
        update={
            "last_finished_test_task": updated_task,
            "current_test_task": None,
            "current_test_case_id": None,
            "messages": [
                ToolMessage(content=success_msg, tool_call_id=tool_call_id)
            ],
        }
    )
