import json
import httpx

from core.commons.logger import logger
from global_config import AI_SERVICE_URL


def construct_notice_payload(task_id: str, user_uid: str, conversation_uid: str, status: str, result: str, payload: dict):
    return {
        'task_id': task_id,
        'client_id': user_uid,
        'history_id': conversation_uid,
        'status': status,
        'result': result,
        'payload': payload,
        'session_id': "",
    }


async def notice_ai(task_info: dict, reason: str, invoke: bool = False):
    """
    Notify AI service about task lifecycle events.
    """
    logger.info(f"[APP][notice_ai] task_info: {task_info}, reason: {reason}")

    if not isinstance(task_info, dict):
        logger.warning("[APP][notice_ai] task_info is not a dict, skip notify.")
        return

    # Minimal required fields check
    required_keys = ("task_id", "client_id", "history_id")
    if not all(task_info.get(k) for k in required_keys):
        logger.warning(
            f"[APP][notice_ai] missing required fields {required_keys}, skip notify."
        )
        return

    if invoke:
        await notice_ai_with_invoke(task_info, reason)
    else:
        await notice_ai_no_invoke(task_info, reason)


async def notice_ai_no_invoke(task_info: dict, reason: str = ""):
    """
    Notify AI service about task info without llm invoking.

    Args:
        task_info (dict): A dictionary containing task information with the following structure:
            {
                "payload": {                 # Optional: Original task payload
                    "tool_name": "string",   # Name of the executed tool
                    "describe": "string",    # Task description
                    "config": {}             # Ai node config include apikey, provider and model. It has the same format with 'config' in method chat_with_llm (ai service).
                    ...                      # Other tool-specific parameters
                },
                "result": list or str,       # Task execution results
                "status": "string",          # Task completion status (e.g., "success", "failed")
                "task_id": "string",         # Unique task identifier
                "client_id": "string",       # Client identifier
                "history_id": "string",      # History session identifier
                "session_id": "string",      # Optional: Session identifier
            }
    """
    payload_info = task_info.get("payload", {})
    if not isinstance(payload_info, dict):
        payload_info = json.loads(payload_info)

    chat_config = payload_info.get("config", {})
    if not isinstance(chat_config, dict):
        chat_config = json.loads(chat_config)

    result = task_info.get("result") or ["No output."]
    status = task_info.get("status")

    if not isinstance(result, list):
        result = json.loads(result)

    merged_result = {
        "status": status,
        "result": result[-1],
    }
    if reason: 
        merged_result.update({
            'reason': reason
        })

    tool_name = payload_info.get("tool_name", "Unnamed task")
    desc = payload_info.get("describe", "None")

    payload = {
        "action": "tool_return",
        "data": {
            "task_id": task_info.get("task_id"),
            "client_id": task_info.get("client_id"),
            "history_id": task_info.get("history_id"),
            "session_id": task_info.get("session_id", ""),
            "messages": {
                "role": "system",
                "content": (
                    f"{tool_name} execute finish. \n"
                    f"task_id: {task_info.get('task_id')}. \n"
                    f"Get result: **{json.dumps(merged_result, ensure_ascii=False)}**"
                ),
                "info": {
                    "task_id": task_info.get("task_id"),
                    "tool_name": tool_name,
                    "desc": desc,
                    "status": status,
                },
            },
            "config": chat_config
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{AI_SERVICE_URL}/api/v1/task_info_rtn/no_invoke",
                json=payload,
            )
            resp.raise_for_status()

        logger.info(
            f"[APP][notice_ai_no_invoke] Notify AI success: {resp.status_code}"
        )

    except Exception as e:
        logger.exception(f"[APP][notice_ai_no_invoke] Fail: {e}")


async def notice_ai_with_invoke(task_info: dict, reason: str = ""):
    """
    Notify AI service about task info with llm invoking.
    
    Args:
        task_info (dict): A dictionary containing task information with the following structure:
            {
                "payload": {                 # Optional: Original task payload
                    "tool_name": "string",   # Name of the executed tool
                    "describe": "string",    # Task description
                    ...                      # Other tool-specific parameters
                },
                "result": list or str,       # Task execution results
                "status": "string",          # Task completion status (e.g., "success", "failed")
                "task_id": "string",         # Unique task identifier
                "client_id": "string",       # Client identifier
                "history_id": "string",      # History session identifier
                "session_id": "string",      # Optional: Session identifier
            }
    """
    payload_info = task_info.get("payload", {})
    if not isinstance(payload_info, dict):
        payload_info = json.loads(payload_info)

    chat_config = payload_info.get("config", {})
    if not isinstance(chat_config, dict):
        chat_config = json.loads(chat_config)

    result = task_info.get("result") or ["No output."]
    status = task_info.get("status")

    if not isinstance(result, list):
        result = json.loads(result)

    merged_result = {
        "status": status,
        "result": result[-1],
    }
    if reason: 
        merged_result.update({
            'reason': reason
        })

    tool_name = payload_info.get("tool_name", "Unnamed task")
    desc = payload_info.get("describe", "None")

    payload = {
        "action": "tool_return",
        "data": {
            "task_id": task_info.get("task_id"),
            "client_id": task_info.get("client_id"),
            "history_id": task_info.get("history_id"),
            "session_id": task_info.get("session_id", ""),
            "messages": {
                "role": "tools",
                "content": (
                    f"task_id: {task_info.get('task_id')}. User has confirmed.\n"
                    f"{tool_name} execute finish. \n"
                    f"Get result: **{json.dumps(merged_result, ensure_ascii=False)}**"
                ),
                "info": {
                    "task_id": task_info.get("task_id"),
                    "tool_name": tool_name,
                    "desc": desc,
                    "status": status,
                },
            },
            "config": chat_config
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{AI_SERVICE_URL}/api/v1/task_info_rtn/with_invoke",
                json=payload,
            )
            resp.raise_for_status()

        logger.info(
            f"[APP][notice_ai_with_invoke] Notify AI success: {resp.status_code}"
        )

    except Exception as e:
        logger.exception(f"[APP][notice_ai_with_invoke] Fail: {e}")


async def notice_ai_task_expire(task_info: dict):
    """
    Notify AI that a task has expire.
    This method has been deprecated, use notice_ai_no_invoke or notice_ai_with_invoke instead.

    Args:
        task_info (dict): A dictionary containing task information with the following structure:
            {
                "payload": {                 # Optional: Original task payload
                    "tool_name": "string",   # Name of the expired tool
                    "describe": "string",    # Task description
                    ...                      # Other tool-specific parameters
                },
                "task_id": "string",         # Unique task identifier
                "client_id": "string",       # Client identifier
                "history_id": "string",      # History session identifier
                "session_id": "string",      # Optional: Session identifier
            }
    """
    payload_info = task_info.get("payload") or {}
    if not isinstance(payload_info, dict):
        payload_info = {}

    tool_name = payload_info.get("tool_name", "Unnamed task")
    desc = payload_info.get("describe", "None")

    payload = {
        "action": "tool_return",
        "data": {
            "task_id": task_info.get("task_id"),
            "client_id": task_info.get("client_id"),
            "history_id": task_info.get("history_id"),
            "session_id": task_info.get("session_id", ""),
            "messages": {
                "role": "system",
                "content": (
                    f"{tool_name} expired. \n"
                    f"Expired task_id: {task_info.get('task_id')}. \n"
                ),
                "extra": {
                    "task_id": task_info.get("task_id"),
                    "tool_name": tool_name,
                    "desc": desc,
                    "status": "fail",
                },
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{AI_SERVICE_URL}/api/v1/task_info_rtn/no_invoke",
                json=payload,
            )
            resp.raise_for_status()

        logger.info(
            f"[APP][notice_ai_task_expire] Notify AI success: {resp.status_code}"
        )

    except Exception as e:
        logger.exception(f"[APP][notice_ai_task_expire] Fail: {e}")
