import asyncio
from typing import Dict, Any, Callable, Awaitable


async def check_health(
    task_id: str,
    payload: Dict[str, Any],
    progress_cb: Callable[[int, str], Awaitable[None]],
) -> Dict[str, Any]:
    """
    Perform a system health check.

    This tool is invoked by the AI agent to verify whether the full chain
    is functioning correctly. The health check simulates a time-consuming
    operation and reports progress periodically.

    Call flow overview:

                                                ├─────→ user client ←─────┤
             (ai receive task result, info user)|           ↓             | (after receive task id, ai info user task submitted)
                                                ├─────→ AI server ←───────┤
                                                |           ↓             | (return task id to ai first)
       (memory server info ai when task is done)|       tool server ──────┤
                                                |           ↓
                                                ├────── memory server

    Args:
        task_id:
            Unique identifier of the task assigned by the AI system.

        payload:
            Optional parameters for the health check, include task info, such 
            as task name, params, etc.
            Currently unused, reserved for future extensions.

        progress_cb:
            Asynchronous callback used to report task progress
            as an integer percentage (0–100).

    Returns:
        A dictionary containing the health check result.
        Example:
            {
                "latency_sec": 10.0
                "output": "..."
            }
    """
    total_steps = 30

    for i in range(total_steps):
        await asyncio.sleep(1)
        await progress_cb(int((i + 1) / total_steps * 100), "")

    return {
        "latency_sec": float(total_steps),
        "output": "System health check finish: NORMAL",
    }
