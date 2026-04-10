from datetime import datetime, timezone
import hashlib
import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx

import global_config as gc
from core.task_manager import task_manager

router = APIRouter(tags=["execute"])


# ----------------------------------------------------------------------
# Health check task
# ----------------------------------------------------------------------

@router.post("/execute/health")
async def check_health(request_data: Request):
    """
    Submit a health-check task and return a task id.

    This API only submits the task.
    Actual execution is handled asynchronously by TaskManager.

    Request Body (JSON):
    {
        "tool_name": "string",           # Required: Name of the tool/check to execute
        "client_id": "string",           # Required: Client identifier
        "history_id": "string",          # Required: History session identifier
        "payload": {                     # Optional: Additional parameters
            "describe": "string",        # Optional: Task description
            "timestamp": "string",       # Optional: Timestamp for the task
            ...                          # Other tool-specific parameters
        }
    }

    Returns (JSON):
    {
        "message": "string",             # Success/status message
        "task_id": "string"              # Unique identifier for the submitted task
    }

    Raises:
        HTTPException 400: If required fields (tool_name, client_id, history_id) are missing
        HTTPException 500: If task creation in memory service fails
    """
    data = None
    try:
        data = await request_data.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    print(f"[check_health] Get data: {data}")

    tool_name = data.get("tool_name")
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    client_id = data.get("client_id", "")
    history_id = data.get("history_id", "")

    if not client_id or not history_id:
        raise HTTPException(status_code=400, detail="client_id and history_id are required")
    
    task_id = str(uuid.uuid4())
    payload = data.get("payload", {})

    describe = None
    timestamp = None
    config = None
    if payload: 
        params = payload.get("params", None)
        describe = payload.get("describe", None)
        timestamp = payload.get("timestamp", None)
        config = payload.get("config", None)

    # Build task_hash: client_id + history_id
    raw_hash = f"{client_id}:{history_id}:{tool_name}"
    task_hash = hashlib.sha1(raw_hash.encode("utf-8")).hexdigest()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. create task in memory service
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            f"{gc.MEMORY_BASE_URL}/memory/task/create",
            json={
                "task_hash": task_hash,
                "task_id": task_id,
                "client_id": client_id,
                "history_id": history_id,
                "payload": {
                    "tool_name": tool_name,
                    "params": params,
                    "describe": describe,
                    "timestamp": timestamp,
                    "config": config,
                },
                "status": "pending",
                "result": {},
                "created_at": now,
                "finished_at": "",
            },
        )

        if resp.status_code != 200:
            print("❌ MEMORY SERVICE ERROR")
            print("url:", f"{gc.MEMORY_BASE_URL}/memory/task/create")
            print("status:", resp.status_code)
            print("body:", resp.text)
            raise HTTPException(status_code=500, detail="Failed to create task: Memory server error.")

        resp_data = resp.json()
        if not resp_data.get("success", False):
            # Memory may reject duplicate task_hash
            return JSONResponse(
                content={
                    "message": resp_data.get("messages", "Task already exists."),
                    "task_id": task_id,
                },
                status_code=200,
            )

    # 2. submit task to TaskManager queue
    await task_manager.submit_task(
        task_id=task_id,
        task_hash=task_hash,
        tool=tool_name,
        payload=payload,
    )

    return JSONResponse(
        content={
            "message": "Submit task success, please wait for User confirming.",
            "task_id": task_id,
        },
        status_code=200,
    )


# ----------------------------------------------------------------------
# Generic task execution (aligned with health check)
# ----------------------------------------------------------------------

@router.post("/execute/task")
async def execute_task(request_data: Request):
    """
    Submit a generic tool task and return a task id.

    This API is aligned with check_health:
    - Same task model
    - Same memory protocol
    - Same TaskManager submission flow

    Request Body (JSON):
    {
        "tool_name": "string",           # Required: Name of the tool/function to execute
        "client_id": "string",           # Required: Client identifier
        "history_id": "string",          # Required: History session identifier
        "payload": {                     # Optional: Tool-specific parameters and data
            "describe": "string",        # Optional: Task description
            "timestamp": "string",       # Optional: Timestamp for the task
            ...                          # Other tool-specific parameters
        }
    }

    Returns (JSON):
    {
        "message": "string",             # Success/status message
        "task_id": "string"              # Unique identifier for the submitted task
    }

    Raises:
        HTTPException 400: If required fields (tool_name, client_id, history_id) are missing
        HTTPException 500: If task creation in memory service fails
    """
    data = None
    try:
        data = await request_data.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    tool_name = data.get("tool_name")
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    client_id = data.get("client_id", "")
    history_id = data.get("history_id", "")

    if not client_id or not history_id:
        raise HTTPException(status_code=400, detail="client_id and history_id are required")

    task_id = str(uuid.uuid4())
    payload = data.get("payload", {})

    # Optional meta fields
    describe = None
    timestamp = None
    config = None
    if payload:
        params = payload.get("params", None)
        describe = payload.get("describe", None)
        timestamp = payload.get("timestamp", None)
        config = payload.get("config", None)

    # Build task_hash: client_id + history_id + tool_name
    raw_hash = f"{client_id}:{history_id}:{tool_name}"
    task_hash = hashlib.sha1(raw_hash.encode("utf-8")).hexdigest()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 1. create task in memory service
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            f"{gc.MEMORY_BASE_URL}/memory/task/create",
            json={
                "task_hash": task_hash,
                "task_id": task_id,
                "client_id": client_id,
                "history_id": history_id,
                "payload": {
                    "tool_name": tool_name,
                    "params": params,
                    "describe": describe,
                    "timestamp": timestamp,
                    "config": config,
                },
                "status": "pending",
                "result": {},
                "created_at": now,
                "finished_at": "",
            },
        )

        if resp.status_code != 200:
            print("❌ MEMORY SERVICE ERROR")
            print("url:", f"{gc.MEMORY_BASE_URL}/memory/task/create")
            print("status:", resp.status_code)
            print("body:", resp.text)
            raise HTTPException(status_code=500, detail="Failed to create task: Memory server error.")

        resp_data = resp.json()
        if not resp_data.get("success", False):
            # Memory may reject duplicate task_hash
            return JSONResponse(
                content={
                    "message": resp_data.get("messages", "Last task does not finish,") + ' Please stop submit.',
                    "task_id": task_id,
                },
                status_code=200,
            )

    # 2. submit task to TaskManager queue
    await task_manager.submit_task(
        task_id=task_id,
        task_hash=task_hash,
        tool=tool_name,
        payload=payload,
    )

    return JSONResponse(
        content={
            "message": "Submit task success, please wait for User confirming.",
            "task_id": task_id,
        },
        status_code=200,
    )
