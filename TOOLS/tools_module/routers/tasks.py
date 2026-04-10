from datetime import datetime, timezone
import hashlib
import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx

import global_config as gc
from core.task_manager import task_manager

router = APIRouter(tags=["task"])


# ----------------------------------------------------------------------
# Task ctrl
# ----------------------------------------------------------------------

@router.post("/task/start")
async def start_task(request_data: Request):
    """
    Manually start a pending task.

    This endpoint is used to explicitly trigger task execution after the task
    has been created and placed into the waiting queue.

    Request Body (JSON):
    {
        "task_id": "string"              # Required: Task identifier to start
    }

    Returns (JSON):
    {
        "success": boolean,              # True if task was successfully started
        "task_id": "string"              # Task identifier that was attempted to start
    }

    Raises:
        HTTPException 400: If request body is invalid JSON or task_id is missing
        HTTPException 404: If task is not found or has already been started
    """
    data = None
    try:
        data = await request_data.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    task_id = data.get("task_id")

    if not task_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: task_id",
        )

    try:
        # Start task
        started = await task_manager.task_start(task_id)

        if not started:
            raise 
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"Task status invalid: {task_id}",
        )

    return JSONResponse(
        {
            "success": True,
            "task_id": task_id,
        }
    )



@router.post("/task/kill")
async def kill_task(request_data: Request):
    """
    Manually kill a task.

    This endpoint terminates a task in the TaskManager and updates its status
    in the memory service. Both client_id and history_id are required to 
    compute the task_hash for identifying the task in memory service.

    Request Body (JSON):
    {
        "tool_name": "string"           # Required
        "task_id": "string",            # Required: Task identifier to kill
        "client_id": "string",          # Required: Client identifier
        "history_id": "string"          # Required: History session identifier
    }

    Returns (JSON):
    {
        "success": boolean,             # True if task was successfully killed
        "task_id": "string"             # Task identifier that was killed
    }

    Raises:
        HTTPException 400: If request body is invalid JSON or required fields are missing
        HTTPException 500: If memory service fails to update task status
    """
    data = None
    try:
        data = await request_data.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    task_id = data.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    tool_name = data.get("tool_name")
    if not task_id:
        raise HTTPException(status_code=400, detail="tool_name is required")

    client_id = data.get("client_id", "")
    history_id = data.get("history_id", "")

    if not client_id or not history_id:
        raise HTTPException(status_code=400, detail="client_id and history_id are required")
    # Build task_hash: client_id + history_id
    raw_hash = f"{client_id}:{history_id}:{tool_name}"
    task_hash = hashlib.sha1(raw_hash.encode("utf-8")).hexdigest()

    # Kill task
    await task_manager.kill_task(task_id)

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            f"{gc.MEMORY_BASE_URL}/memory/task/kill",
            json={
                "task_hash": task_hash,
                "task_id": task_id,
            },
        )

        if resp.status_code != 200:
            print("❌ MEMORY SERVICE ERROR")
            print("url:", f"{gc.MEMORY_BASE_URL}/memory/task/kill")
            print("status:", resp.status_code)
            print("body:", resp.text)
            raise HTTPException(status_code=500, detail="Failed to kill task")

    return JSONResponse(
        {
            "success": True,
            "task_id": task_id,
        }
    )