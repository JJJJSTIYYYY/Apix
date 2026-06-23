import hashlib
import base64
from uuid import uuid4

from fastapi import APIRouter, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from pydantic import BaseModel
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

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

# ==============================
# Symmetric encryption config
# ==============================
# NOTE:
# The key must be exactly the same as the one used on the client side.
# 16 / 24 / 32 bytes for AES-128 / 192 / 256
AES_KEY = b"0123456789abcdef"  # example key, replace in production
AES_IV = b"abcdef9876543210"   # example IV, replace in production


# ==============================
# Models
# ==============================
class RegisterRequest(BaseModel):
    username: str
    password: str  # encrypted password from client


class LoginRequest(BaseModel):
    username: str
    password: str  # encrypted password from client


# ==============================
# Utility functions
# ==============================

def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt password from client using AES-CBC.
    The input is assumed to be base64 encoded.
    """
    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        encrypted_bytes = base64.b64decode(encrypted_password)
        decrypted = cipher.decrypt(encrypted_bytes)
        return unpad(decrypted, AES.block_size).decode("utf-8")
    except Exception:
        # Intentionally vague to avoid leaking crypto details
        raise HTTPException(status_code=400, detail="Invalid encrypted password")


def sha256_hash(raw_password: str) -> str:
    """
    Hash plaintext password using SHA256.
    """
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


@router.post("/auth/register")
async def register(req: RegisterRequest):
    """
    Register a new user.

    Flow:
    1. Generate random 9-digit user_uid
    2. Decrypt password
    3. SHA256 hash
    4. Store into database
    5. Return generated user_uid
    """
    logger.info(f"[API][register] enter.")
    # Decrypt and hash password
    plain_password = decrypt_password(req.password)
    password_hash = sha256_hash(plain_password)
    user_uid = uuid4().hex[:9]  # Generate random 9-digit user_uid

    payload = {
        "client_id": user_uid,
        "username": req.username,
        "password": password_hash
    }

    query_id = await dsm.submit_query(
        action="create_a_user",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)

    return JSONResponse(
        content=resp,
        status_code=200,
    )



@router.post("/auth/login")
async def login(req: LoginRequest):
    """
    User login.

    Flow:
    1. Decrypt password
    2. SHA256 hash
    3. Compare with stored hash
    """
    logger.info(f"[API][login] enter.")
    plain_password = decrypt_password(req.password)
    password_hash = sha256_hash(plain_password)

    payload = {
        "username": req.username,
        "password": password_hash
    }

    query_id = await dsm.submit_query(
        action="verify_user",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)

    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/auth/ensure_user")
async def ensure_user_exists(req: Request):
    """
    Ensure user exists in system.

    Behavior:
    - Insert user if not exists
    - Update user info if already exists

    Request Body (JSON):
        {
            "client_id": str,
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

# --------------------------------------------------
# Conversation
# --------------------------------------------------

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
                    "is_pinned": bool,
                    "has_new_message": bool
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
            "title": "Conversation title",
            "workspace": "Agent work dir",
            "is_pinned": bool,
            "is_deleted": bool,
            "has_new_message": bool
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

# --------------------------------------------------
# Message
# --------------------------------------------------

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
            ] | str
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

@router.post("/memory/user/current_chain_id")
async def current_chain_id(req: Request):
    """
    Fetch the cached node id chain of the user's current message branch.

    Request Body (JSON):
        {
            "client_id": str,
            "history_id": str
        }

    Returns:
        {
            "success": bool,
            "messages": str | list,
            "cache_hit": bool
        }
    """
    logger.info(f"[API][current_chain_id] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_current_messages_branch_chain",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )

# --------------------------------------------------
# Provider Management
# --------------------------------------------------

@router.post("/provider/create_llm_provider")
async def create_llm_provider(req: Request):
    """
    Insert a provider's meta in database.

    Request Body (JSON):
        {
            "client_id": str,
            "provider_name": str,
            "type": str,
            "endpoint": str,
            "model_list": str,
            "description": str,
        }

    Returns:
        {
            "success": bool,
            "messages": {
                "provider_id": str
            }
        }
    """
    logger.info(f"[API][create_llm_provider] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="create_llm_provider",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )



@router.post("/provider/get_llm_providers")
async def get_llm_providers(req: Request):
    """
    Fetch all providers meta for user.

    Request Body (JSON):
        {
            "client_id": str,
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "provider_id": str,
                    "provider_name": str,
                    "type": str,
                    "endpoint": str,
                    "model_list": list,
                    "description": str,
                    "created_at": str
                },
                ...
            ]
        }
    """
    logger.info(f"[API][get_llm_providers] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_llm_providers",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )



@router.post("/provider/get_llm_provider_by_id")
async def get_llm_provider_by_id(req: Request):
    """
    Fetch a provider meta by provider_id. 

    Request Body (JSON):
        {
            "provider_id": str
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "provider_id": str,
                    "provider_name": str,
                    "type": str,
                    "endpoint": str,
                    "model_list": list,
                    "description": str,
                    "created_at": str
                },
                ...
            ]
        }
    """
    logger.info(f"[API][get_llm_provider_by_id] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_llm_provider_by_id",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )



@router.post("/provider/update_llm_provider")
async def update_llm_provider(req: Request):
    """
    Update or delete a provider's meta.

    Request Body (JSON):
        {
            "provider_id": str,
            "client_id": str,
            "provider_name": str, # Optional
            "type": str, # Optional
            "endpoint": str, # Optional
            "model_list": str, # Optional
            "description": str, # Optional
            "is_deleted": bool, # Optional
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info(f"[API][update_llm_provider] enter.")
    payload = await req.json()

    query_id = await dsm.submit_query(
        action="update_llm_provider",
        payload=payload,
    )
    result = await dsm.wait_result(query_id)
    resp = jsonable_encoder(result)
    return JSONResponse(
        content=resp,
        status_code=200,
    )

# --------------------------------------------------
# MCP Server
# --------------------------------------------------

@router.post("/mcp/create_mcp_server")
async def create_mcp_server(req: Request):
    """
    Insert a mcp server meta in database.

    Request Body (JSON):
        {
            "client_id": str,
            "mcp_name": str,
            "transport": str,
            "endpoint": str,
            "config": dict,
            "description": str,
        }

    Returns:
        {
            "success": bool,
            "messages": {
                "mcp_id": str
            }
        }
    """
    logger.info("[API][create_mcp_server] enter.")

    payload = await req.json()

    query_id = await dsm.submit_query(
        action="create_mcp_server",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    resp = jsonable_encoder(result)

    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/mcp/get_mcp_servers")
async def get_mcp_servers(req: Request):
    """
    Fetch all mcp server meta for user.

    Request Body (JSON):
        {
            "client_id": str
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "mcp_id": str,
                    "mcp_name": str,
                    "transport": str,
                    "endpoint": str,
                    "config": dict,
                    "description": str,
                    "enabled": bool,
                    "tool_count": int,
                    "created_at": str
                }
            ]
        }
    """
    logger.info("[API][get_mcp_servers] enter.")

    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_mcp_servers",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    resp = jsonable_encoder(result)

    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/mcp/get_enabled_mcp_servers")
async def get_enabled_mcp_servers(req: Request):
    """
    Fetch enabled mcp servers for user.

    Request Body (JSON):
        {
            "client_id": str
        }

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "mcp_id": str,
                    "mcp_name": str,
                    "transport": str,
                    "endpoint": str,
                    "config": dict
                }
            ]
        }
    """
    logger.info("[API][get_enabled_mcp_servers] enter.")

    payload = await req.json()

    query_id = await dsm.submit_query(
        action="get_enabled_mcp_servers",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    resp = jsonable_encoder(result)

    return JSONResponse(
        content=resp,
        status_code=200,
    )


@router.post("/mcp/update_mcp_server")
async def update_mcp_server(req: Request):
    """
    Update or delete a mcp server meta.

    Request Body (JSON):
        {
            "mcp_id": str,
            "client_id": str,

            "mcp_name": str,      # Optional
            "transport": str,     # Optional
            "endpoint": str,      # Optional
            "config": dict,       # Optional
            "description": str,   # Optional

            "enabled": bool,      # Optional
            "tool_count": int,    # Optional

            "is_deleted": bool,   # Optional
        }

    Returns:
        {
            "success": bool,
            "messages": str
        }
    """
    logger.info("[API][update_mcp_server] enter.")

    payload = await req.json()

    query_id = await dsm.submit_query(
        action="update_mcp_server",
        payload=payload,
    )

    result = await dsm.wait_result(query_id)

    resp = jsonable_encoder(result)

    return JSONResponse(
        content=resp,
        status_code=200,
    )