import json
from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.domain.data_server_manager import data_server_manager as dsm
from core.commons.logger import logger

router = APIRouter(tags=["tasks_record"])


"""
All endpoints follow the same execution pattern:

1. Parse request payload
2. Submit task to DataServerManager
3. Await execution result
4. Return normalized response

These endpoints DO NOT contain business logic.
"""


@router.post("/memory/task/create")
async def create_task(req: Request):
    """
    Create a runtime task entry.

    Behavior:
    - Use Redis as a runtime lock
    - Reject creation if task_hash already exists

    Request Body (JSON):
        {
            "task_hash": str,
            "task_id": str,
            "client_id": str,
            "history_id": str,
            "payload": dict, // dict to store task info, such as tool(task) name, params, model and provider etc.
            "status": "pending", // fixed str.
            "result": dict, // the result of the task, it is empty when task created.
            "created_at": str,
            "finished_at": "" // empty str.
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][create_task] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="create_task",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/task/update")
async def update_task(req: Request):
    """
    Update runtime task state.

    Behavior:
    - Update task info in Redis
    - If task reaches finished state:
        * Redis deletes runtime entry
        * Task result is persisted to MySQL

    Request Body (JSON):
        {
            "task_hash": str,
            "task_id": str,
            "status": str,
            "result": dict, // optional, task result, it should be dict.
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][update_task] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="update_task",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/task/kill")
async def kill_task(req: Request):
    """
    Get task information.

    Behavior:
    - Query Redis for running task
    - Fallback to MySQL for finished task

    Path Params:
        {
            "task_hash": str
            "task_id": str
        }

    Returns:
        {
            "success": bool,
            "messages": str,
        }
    """
    logger.info(f"[API][kill_task] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="kill_task",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    resp_1 = json.dumps(resp)
    resp_2 = json.loads(resp_1)
    return JSONResponse(
        content=resp_2,
        status_code=200,
    )



@router.post("/memory/task/info")
async def get_task_info(req: Request):
    """
    Get task information.

    Behavior:
    - Query Redis for running task
    - Fallback to MySQL for finished task

    Path Params:
        {
            "task_hash": str
            "task_id": str
        }

    Returns:
        {
            "success": bool,
            "messages": {
                "task_id": str,
                "conversation_uid": str,
                "status": str,
                "payload": str (dict format),
                "result": str (dict format),
                "created_at": str,
                "finished_at": str
            }
        }
    """
    logger.info(f"[API][get_task_info] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_task_info",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    resp_1 = json.dumps(resp)
    resp_2 = json.loads(resp_1)
    return JSONResponse(
        content=resp_2,
        status_code=200,
    )
