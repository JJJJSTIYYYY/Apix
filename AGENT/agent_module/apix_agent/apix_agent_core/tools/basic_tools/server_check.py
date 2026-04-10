import time
from typing import Annotated

import httpx
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from apix_agent import global_config
from apix_agent.commons.logger import logger


@tool
async def check_server(
    describe: str,
    state: Annotated[dict, InjectedState],
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
    try:
        client_id = state["client_id"]
        session_id = state.get("session_id")
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
        return f"Healthy check task has been submitted: {resp_data}"

    except Exception as e:
        logger.exception("[check_server] submit failed")
        return f"[Error] Failed to submit health check task: {str(e)}"
