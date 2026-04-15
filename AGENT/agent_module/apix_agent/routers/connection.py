import time
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.apix_agent_core.websocket.websocket_manager import websocket_list, ws_msg_handler
from apix_agent.global_config import AGENT_SERVICE_ID
from apix_agent.commons.logger import logger

router = APIRouter(tags=["connection"])


async def _task_info_rtn_no_invoke_background(
    data: dict,
):
    """
    Background coroutine for handling task_info_rtn_no_invoke logic.
    This function MUST NOT raise exceptions to the caller.
    """
    tool_messages = data.get("messages", {})
    tool_task_id = data.get("task_id")
    history_id = data.get("history_id")
    client_id = data.get("client_id")

    try:
        await websocket_list.send_tool_event(tool_task_id, client_id, history_id, tool_messages)

    except Exception as e:
        error_msg = {
            "role": "system",
            "content": f"Error occured: {e}",
        }
        await websocket_list.send_tool_event(tool_task_id, client_id, history_id, error_msg)
        logger.info(f"[task_finish background error] {e}")


@router.post("/api/v1/task_info_rtn/no_invoke")
async def task_info_rtn_no_invoke(request_data: Request):
    '''
    Info the task is finished.
    This api is called by memory module.
    This api do not invoke llm.

    Args:
        request_data (Request): FastAPI request object containing client memory in JSON format.
            JSON structure:
            {
                "action": "tool_return", 
                "data": {
                    "task_id": "...",
                    "client_id": "...",
                    "history_id": "...",
                    "session_id": "...",
                    "messages": {
                        "role": "system",
                        "content": "task_name: describe",  // result is a dict normally, ensure str is sent.
                    }
                }
            }
    Returns:
        JSONResponse: ok.
    '''
    try:
        body = await request_data.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid JSON"},
            status_code=400,
        )

    data = body.get("data", {})
    asyncio.create_task(_task_info_rtn_no_invoke_background(data))

    return JSONResponse(
        content={"messages": "ok"},
        status_code=200,
    )


async def _task_info_rtn_with_invoke_background(
    data: dict,
):
    """
    Background coroutine for handling task_info_rtn_with_invoke logic.
    This function MUST NOT raise exceptions to the caller.
    """
    tool_messages = data.get("messages", {})
    tool_task_id = data.get("task_id")
    session_id = data.get("session_id")
    history_id = data.get("history_id")
    client_id = data.get("client_id")
    config = data.get("config", {})

    try:
        logger.info(f"\n\033[93m[task_info_rtn_with_invoke]\033[0m Tool memory received: {tool_messages}")
        await websocket_list.send_tool_event(tool_task_id, client_id, history_id, tool_messages)

        if not config.get('max_chunk_per_invoking', True): 
            return
            # timestamp = time.time() * 1_000_000
            # tool_messages.update({
            #     "timestamp": timestamp,
            # })
            # await ai_context_manager.append_to_messages(
            #     client_id,
            #     history_id,
            #     tool_messages,
            # )
            # return  # If tool invoking ai is disabled, exit early.

        invoke_payload = {
            "action": "chat_with_llm",
            "data": {
                "client_id": client_id,
                "session_id": session_id,
                "history_id": history_id,
                "messages": tool_messages,
                "config": config
            }
        }

        # ------------------------------
        # Create new generation (this will abort previous one)
        # ------------------------------
        try:
            generation_id = await websocket_list.create_generation(client_id, history_id)
        except Exception as e:
            logger.error(f"[ws] create_generation failed client={client_id}: {e}")
            raise e

        logger.info(
            f"[ws] new generation created: "
            f"client={client_id}, generation={generation_id}"
        )

        # ------------------------------
        # Trigger AI invoke (async / background)
        # ------------------------------
        await ws_msg_handler.chat_with_llm(generation_id, invoke_payload)

    except Exception as e:
        ws_msg_handler.return_error_msg(generation_id, client_id, history_id, f"[_task_info_rtn_with_invoke_background] {e}")
        logger.error(f"[task_finish background error] {e}")
        raise e


@router.post("/api/v1/task_info_rtn/with_invoke")
async def task_info_rtn_with_invoke(request_data: Request):
    '''
    Info the task is finished.
    This api is called by memory module.

    Args:
        request_data (Request): FastAPI request object containing client memory in JSON format.
            JSON structure:
            {
                "action": "msg_return", 
                "data": {
                    "task_id": "...",
                    "client_id": "...",
                    "history_id": "...",
                    "session_id": "...",
                    "messages": {
                        "role": "system",
                        "content": json.dumps(task_info.get("result"))  // result is a dict normally, ensure str is sent.

                    }
                }
            }
    Returns:
        JSONResponse: ok.
    '''
    try:
        body = await request_data.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid JSON"},
            status_code=400,
        )

    data = body.get("data", {})

    # --------------------------------------------------
    # Fire-and-forget background task
    # --------------------------------------------------
    asyncio.create_task(_task_info_rtn_with_invoke_background(data))

    # --------------------------------------------------
    # Immediately return OK to memory module
    # --------------------------------------------------
    return JSONResponse(
        content={"messages": "ok"},
        status_code=200,
    )













