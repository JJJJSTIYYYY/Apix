from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.commons.logger import logger
from app.core.task_manager import task_manager
from app.core.translator import translator


router = APIRouter(tags=["task"])
TaskStatus = Literal["pending", "running", "finished"]


@router.post("/plugin/submit_task")
async def submit_task(request_data: Request):
    """
    Submit a task to task queue.

    Args:
        request_data (Request):
            raw JSON structure is:
            {
                "client_id": str,
                "content": dict | list[dict],
                content supports either a single case tree or a list of case trees.
                A single dict example:
                {
                    "type": "folder",
                    "content": [
                        {
                            "type": "interface",
                            "title": str,
                            "address": str,
                            "description": str,
                        },
                        {
                            "type": "database",
                            "title": str,
                            "address": str,
                            "description": str,
                        },
                        {
                            "type": "script",
                            "title": str,
                            "script": str,
                            "description": str,
                        }
                    ]
                }
                
                list[dict] example:
                [
                    {
                        "type": "interface",
                        "title": str,
                        "address": str,
                        "description": str,
                    },
                    {
                        "type": "folder",
                        "content": [
                            {
                                "type": "script",
                                "title": str,
                                "script": str,
                                "description": str,
                            }
                        ]
                    }
                ]
                "mock": str, # mock data description and value, a string.
            }

    Returns:
        {
            "success": bool,
            "messages": {
                "task_id": str,
                "pending_task": int,
                "running_task": int,
                "finished_task": int
            },
        }
    """
    body = await request_data.json()
    client_id = body.get("client_id")
    raw_content = body.get("content")
    mock = body.get("mock")

    if not client_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "messages": "client_id is required."},
        )

    if raw_content is None:
        return JSONResponse(
            status_code=400,
            content={"success": False, "messages": "content is required."},
        )

    if not isinstance(raw_content, (dict, list)):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "messages": "content must be a dict or list of dicts.",
            },
        )

    try:
        content: list[dict] = []
        raw_cases = raw_content if isinstance(raw_content, list) else [raw_content]

        for raw_case in raw_cases:
            if not isinstance(raw_case, dict):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "messages": "Each content item must be a dict.",
                    },
                )
            content.extend(translator.translate(raw_case))
    except Exception as exc:
        logger.exception("[submit_task] Failed to translate task content.")
        return JSONResponse(
            status_code=400,
            content={"success": False, "messages": str(exc)},
        )

    if not content:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "messages": "No executable task was generated after translation.",
            },
        )

    logger.info(f"[submit_task] Submit task: {client_id} - {len(content)}")

    task_id = await task_manager.submit(client_id, content, mock)
    pending_task = await task_manager.query(client_id, status = "pending")
    running_task = await task_manager.query(client_id, status = "running")
    finished_task = await task_manager.query(client_id, status = "finished")

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "messages": {
                "task_id": task_id,
                "pending_task": len(pending_task),
                "running_task": len(running_task),
                "finished_task": len(finished_task)
            }
        }
    )


@router.post("/plugin/query_task")
async def query_task(request_data: Request):
    """
    Query tasks by client ID and status.

    Args:
        request_data (Request):
            JSON structure:
            {
                "client_id": str,
                "status": Literal["pending", "running", "finished"],
            }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "id": str,
                    "task_id": str,
                    "client_id": str,
                    "mock": str,
                    "name": str,
                    "type": str,
                    "address": str,
                    "script": str,
                    "description": str,
                    "status": Literal["pending", "running", "finished"],
                    "result": str,
                }
            ],
        }
    """
    body = await request_data.json()
    client_id = body.get("client_id")
    status_list = body.get("status")
    if isinstance(status_list, str):
        status_list = [status_list]

    if not client_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "messages": "client_id is required."},
        )

    tasks = []
    for status in status_list:
        if status not in {"pending", "running", "finished"}:
            return JSONResponse(
                status_code=400,
                content={"success": False, "messages": "Invalid status value."},
            )

        logger.info(f"[query_task] Query task: {client_id} - {status}")
        tasks = tasks + (await task_manager.query(client_id, status=status))

    return JSONResponse(
        status_code=200,
        content={"success": True, "messages": tasks},
    )


@router.post("/plugin/get_task")
async def get_task(request_data: Request):
    """
    Get one pending task and move it to the running queue.

    Returns:
        {
            "success": bool,
            "messages": {
                "task": [
                    {
                        "id": str,
                        "task_id": str,
                        "client_id": str,
                        "mock": str,
                        "name": str,
                        "type": str,
                        "address": str,
                        "script": str,
                        "description": str,
                        "status": Literal["running"],
                        "result": str,
                    }
                ],
                "pending_task": int,
                "running_task": int,
                "finished_task": int,
            },
        }
    """
    logger.info("[get_task] Get one pending task.")
    body = await request_data.json()
    client_id = body.get("client_id")

    try:
        task = await task_manager.get()
    except Exception as exc:
        logger.exception("[get_task] Failed to get task.")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(exc)},
        )
    
    pending_task = await task_manager.query(client_id, status = "pending")
    running_task = await task_manager.query(client_id, status = "running")
    finished_task = await task_manager.query(client_id, status = "finished")

    return JSONResponse(
        status_code=200,
        content={
            "success": True, 
            "messages": {
                "task": task,
                "pending_task": len(pending_task),
                "running_task": len(running_task),
                "finished_task": len(finished_task)
            }
        },
    )


@router.post("/plugin/update_task")
async def update_task(request_data: Request):
    """
    Update one running task to finished.

    Args:
        request_data (Request):
            JSON structure:
            {
                "id": str,
                "result": str,
                "status": Literal["finished"], # optional
            }

    Returns:
        {
            "success": bool,
            "messages": {
                "id": str,
                "task_id": str,
                "client_id": str,
                "mock": str,
                "name": str,
                "type": str,
                "address": str,
                "script": str,
                "description": str,
                "status": Literal["finished"],
                "result": str,
            },
        }
    """
    body = await request_data.json()
    task_id = body.get("id")
    result = body.get("result", "")
    status: TaskStatus = body.get("status", "finished")

    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "messages": "id is required."},
        )

    if status != "finished":
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "messages": "Only the 'finished' status is allowed.",
            },
        )

    logger.info(f"[update_task] Update task: {task_id} - {status}")

    try:
        task = await task_manager.update(task_id, result, status=status)
    except (KeyError, ValueError) as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "messages": str(exc)},
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "messages": task},
    )
