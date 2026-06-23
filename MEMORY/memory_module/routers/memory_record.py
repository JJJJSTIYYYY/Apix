from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.domain.data_server_manager import data_server_manager as dsm
from core.commons.logger import logger


router = APIRouter(tags=["memory_record"])


"""
All endpoints follow the same execution pattern:

1. Parse request payload
2. Submit task to DataServerManager
3. Await execution result
4. Return normalized response

These endpoints DO NOT contain business logic.
"""


@router.post("/memory/memory/append_message")
async def append_message(req: Request):
    """
    Append a single message to conversation memory.

    Behavior:
    - Persist message to MySQL (source of truth)
    - Best-effort append message to Redis cache if exists

    Request Body (JSON):
        {
            "client_id": str,
            "history_id": str,
            "session_id": str,
            "messages": {
                "role": 'human', 'ai', 'system', 'tool',
                "content": str,
                "think": str,  # optional
                "extra": {...}  # optional extra metadata
                "info": {
                    "model": "...",
                    "total_duration": "...",
                    "model_provider": "...",
                    "total_tokens": int,
                    "id": "",
                }, 
                "timestamp": int,
                "generation_id": str,
                "node_id": str,
                "parent_id": str
            }
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][append_message] enter.")
    payload = await req.json()
    logger.info(f"[API][append_message] payload:\n{payload}")

    query_id = await dsm.submit_query(
        action="append_message",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/memory/delete_messages")
async def delete_messages(req: Request):
    """
    Delete one oe more message in database.

    Behavior:
    - Delete message from MySQL (source of truth)
    - Expire cache in Redis if exists

    Request Body (JSON):
        {
            "client_id": str,
            "history_id": str,
            "session_id": str,
            "messages": [  # list of message generation_id and role
                str # node_id
            ]
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][delete_messages] enter.")
    payload = await req.json()
    logger.info(f"[API][delete_messages] payload:\n{payload}")

    query_id = await dsm.submit_query(
        action="delete_messages",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/memory/messages")
async def get_messages(req: Request):
    """
    Fetch conversation messages after a given cursor.

    Behavior:
    - Try fetch from Redis first
    - Fallback to MySQL on cache miss
    - Backfill Redis if needed

    Request Body (JSON):
        {
            "client_id": str,
            "history_id": str,
            "session_id": str (optional),
            "cursor": int,
            "current_node_id": str,
            "limit": int (optional)
        }

    Returns:
        {
            "success": bool,
            "cache_hit": bool (optional),
            "next_cursor": int,
            "messages": [
                {
                    "role": str,
                    "content": str,
                    "extra": str (list of dict format),
                    "msg_cursor": int,
                    "created_at": str
                }
            ]
        }
    """
    logger.info(f"[API][get_messages] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_messages",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/memory/search_messages_by_keyword")
async def search_messages_by_keyword(req: Request):
    """
    Search messages in all conversations by keyword.

    Request Body (JSON):
        {
            "client_id": str,
            "keyword": str
        }

    Returns:
        {
            "success": True / False,
            "messages": [
                {
                    "conversation_uid": str,
                    "generation_id": str,
                    "role": str,
                    "title": str,
                    "content": str,
                    "last_active_at": str
                },
                ...
            ]
        }
    """
    logger.info(f"[API][search_messages_by_keyword] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="search_messages_by_keyword",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/memory/shortterm")
async def get_shortterm(req: Request):
    """
    Fetch shortterm memories.
    Limit 1.

    Request Body (JSON):
        {
            "client_id": str,
            "history_id": str,
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "memory_id": str,
                    "content": str,
                    "created_timestamp": int,
                }
            ]
        }
    """
    logger.info(f"[API][get_shortterm] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="fetch_shortterm_memory",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/memory/insert_shortterm")
async def insert_shortterm(req: Request):
    """
    Insert shortterm memories.

    Request Body (JSON):
        {
            "memory_id": str,
            "client_id": str,
            "history_id": str,
            "content": str,
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][get_shortterm] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="insert_shortterm_memory",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/memory/conversation/create")
async def create_new_conversation(req: Request):
    """
    Create a new conversation.

    Behavior:
    - Ensure user exists in MySQL
    - Create a new conversation record
    - No Redis interaction

    Request Body (JSON):
        {
            "client_id": str,
            "platform": str,
            "session_id": str (optional),
            "title": str (optional),
            "workspace": str (optional),
        }

    Returns:
        {
            "success": bool,
            "messages": str # conversation_uid
        }
    """
    logger.info(f"[API][create_new_conversation] enter.")
    payload = await req.json()
    query_id = await dsm.submit_query(
        action="create_new_conversation",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )
