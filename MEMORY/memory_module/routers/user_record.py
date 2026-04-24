from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.domain.data_server_manager import data_server_manager as dsm
from core.commons.logger import logger


router = APIRouter(tags=["user_record"])


"""
All endpoints follow the same execution pattern:

1. Parse request payload
2. Submit task to DataServerManager
3. Await execution result
4. Return normalized response

These endpoints DO NOT contain business logic.
"""


@router.post("/memory/user/ensure")
async def ensure_user_exists(req: Request):
    """
    Ensure user exists in system.

    Behavior:
    - Insert user if not exists
    - Update user info if already exists

    Request Body (JSON):
        {
            "client_id": str,
            "username": str (optional)
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][ensure_user_exists] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="ensure_user_exists",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/user/conversations/list")
async def fetch_conversation_list(req: Request):
    """
    Fetch user's conversation list.

    Behavior:
    - Query conversation list from MySQL
    - Used for displaying conversation history panel

    Request Body (JSON):
        {
            "client_id": "{{ cid }} : to indicate which user the data is from.",
            "session_id": "{{ sid }} : to indicate which tab the data belong to",
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "conversation_uid": str,
                    "session_id": str,
                    "title": str,
                    "last_active_at": str,
                    "created_at": str,
                    "latest_cursor": int,
                    "is_pinned": int (tinny_int)
                },
                ...
            ]
        }
    """
    logger.info(f"[API][fetch_conversation_list] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="fetch_conversation_list",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/memory/user/conversations/update")
async def update_conversation(req: Request):
    """
    Update a conversation such as change title, pin and connect with new tab.

    Behavior:
    - Update conversation in MySQL.

    Request Body (JSON):
        {
            "client_id": "{{ cid }} : to indicate which user the data is from.",
            "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
            "session_id": "{{ sid }} : to indicate which tab the data belong to",
            "title": "conversation title",
            "is_pinned": bool,
            "is_deleted": bool,
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    payload = await req.json()
    logger.info(f"[API][update_conversation] enter.\nclient_id: {payload.get('client_id', "client_id empty.")}\nhistory_id: {payload.get('history_id', "history_id empty.")}")

    query_id = await dsm.submit_query(
        action="update_conversation",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )



@router.post("/memory/user/messages")
async def get_messages_for_user(req: Request):
    """
    Fetch conversation messages for user.

    Behavior:
    - Get all ai % user (human) messages in target conversation.
    - Get all task info in target conversation.
    - Merge and sort brfore return to client.

    Request Body (JSON):
        {
            "client_id": str,
            "history_id": str,
            "current_node_id": str,
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "role": str,
                    "content": str,
                    "think": str,
                    "extra": str (dict format),
                    "msg_cursor": int,
                    "created_at": str
                },
                ...
            ]
        }
    """
    logger.info(f"[API][get_messages_for_user] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_messages_for_user",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )