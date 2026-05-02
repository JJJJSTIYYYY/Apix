import time
from typing import Annotated

import httpx
from langchain.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent import global_config
from apix_agent.commons.logger import logger


@tool
async def check_server(
    describe: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """
    Check the system health.
    The health check task will be submitted to the tools service
    and the result will be returned later.

    This tool submits a health-check task to the tools service.
    The execution result will be pushed asynchronously.
    If submission is successful, a task will be created and a task_id will be returned.

    Args:
        describe (str): A simple sentence to describe this task.

    Returns:
        str: task_id of the health-check task

    ## When to Use This Tool
    Use this tool only when the user explicitly asks to check the system health.
    ## When NOT to Use This Tool
    Do NOT use this tool when the user does not explicitly ask to check the system health, even if you suspect there might be some issues with the system.
    """
    logger.trace('[server_check.py] [tool] [check_server] Enter')
    client_id = state.get("client_id")
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "check_server",
            "tool_call_id": tool_call_id,
            "content": "Check tools server",
            "chunk_position": "start",
            "status": "success",
        }
    )
    
    try:
        history_id = state["history_id"]
        config = state["config"]

        data = {
            "tool_name": "ServerCheck",
            "client_id": client_id,
            "history_id": history_id,
            "payload": {
                "describe": describe,
                "timestamp": time.time(),
                "config": config,
                "params": {},
            },
        }

        logger.info(f"[check_server] submit payload: {data}")

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{global_config.TOOLS_SERVICE_URL}/execute/health",
                json=data,
            )

        resp_data = resp.json()

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "check_server",
                "tool_call_id": tool_call_id,
                "content": "Check tools server task submitted",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(f"Healthy check task has been submitted: {resp_data}", tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "check_server",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        logger.exception("[check_server] submit failed")
        return Command(update={
            "messages": [
                ToolMessage(f"[Error] Failed to submit health check task: {str(e)}", tool_call_id=tool_call_id)
            ]
        })
