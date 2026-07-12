from datetime import datetime
from typing import Literal
import httpx
import inflect

from apix_agent.commons.logger import logger
from apix_agent.global_config import MEMORY_SERVICE_BASE_URL


def get_date_natural_language():
    now = datetime.now()
    
    day = now.day
    month = now.strftime("%B")
    year = now.year
    weekday = now.strftime("%A")
    
    p = inflect.engine()
    ordinal_day = p.ordinal(day)
    
    # "Wednesday, April 15th, 2026"
    natural_date = f"DATE: {weekday}, {month} {ordinal_day}, {year}"
    
    return natural_date


def convert_generation_id_to_message_node_id(
    generation_id: str | list[str] | set[str],
    role: Literal['user', 'human', 'ai', 'assistant']
) -> str | list[str] | set[str]:
    suffix = "-user" if role in ['user', 'human'] else "-apix"

    def convert(gid: str) -> str:
        return gid[-12:] + suffix

    if isinstance(generation_id, str):
        return convert(generation_id)

    return type(generation_id)(
        convert(gid)
        for gid in generation_id
    )


async def get_conversation_meta(conversation_id) -> dict:
    """Get the conversation's metadata path from database.
    
    Returns:
    {
        "conversation_uid": str,
        "session_id": str,
        "title": str,
        "work_space": str,
        "last_active_at": str,
        "created_at": str,
        "latest_cursor": int,
        "is_pinned": bool,
        "has_new_message": bool
    }
    """
    async with httpx.AsyncClient() as client:

        response = await client.post(
            f"{MEMORY_SERVICE_BASE_URL}/memory/user/conversations/meta",
            json={
                "history_id": conversation_id,
            },
        )

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError(
            data.get("messages") or
            "Failed to get conversation meta."
        )

    if not isinstance(data["messages"], list):
        logger.error(f"Unsupported meta format: {type(data["messages"]).__name__}")
        return {}

    if not data["messages"]:
        logger.warning(f"No metadata got for conversation {conversation_id}")
        return {}

    return data["messages"][0]


async def get_conversation_workspace(conversation_id) -> str:
    """Get the conversation's workspace path from database."""
    try:
        conversation_meta = await get_conversation_meta(conversation_id)
    except Exception:
        logger.error(f"Failed to get workspace for conversation {conversation_id}")
        return ""

    return conversation_meta.get("work_space", "")