import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import traceback

from apix_agent.apix_agent_core.websocket.websocket_manager import websocket_list, ws_msg_handler
from apix_agent.commons.logger import logger


router = APIRouter(tags=["websocket"])

@router.websocket("/ws/{client_id}")
async def ws_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    logger.success(f"[ws] client connected: {client_id}")

    try:
        await websocket_list.register(websocket, client_id)
    except Exception as e:
        logger.error(f"[ws] register failed for client={client_id}: {e}")
        await websocket.close()
        return

    try:
        while True:
            raw_data = await websocket.receive_text()
            logger.info(f"[ws] recv from client={client_id}: {raw_data}")

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                logger.error(f"[ws] invalid json from client={client_id}")
                continue

            action = data.get("action")

            # ------------------------------
            # Create new generation (this will abort previous one)
            # ------------------------------

            try:
                temp = data.get("data") or {}
                history_id = temp.get("history_id")
                generation_id = await websocket_list.create_generation(client_id, history_id, append_cache_memory=(action=="chat_with_llm"))
            except Exception as e:
                logger.error(f"[ws] create_generation failed client={client_id}: {e}")
                continue

            logger.info(
                f"[ws] new generation created: "
                f"client={client_id}, generation={generation_id}"
            )

            # ------------------------------
            # Trigger AI invoke (async / background)
            # ------------------------------

            if action == "chat_with_llm":
                asyncio.create_task(ws_msg_handler.chat_with_llm(generation_id, data))
            elif action == "abort_generation":
                pass
            else:
                raise ValueError(f"unknown action: {action}")

    except WebSocketDisconnect:
        logger.info(f"[ws] client disconnected: {client_id}")

    except Exception as e:
        logger.error(
            "[ws] unexpected error for client="+
            f"{client_id}: {e}\n{traceback.format_exc()}"
        )

    finally:
        websocket_list.unregister(client_id)
        logger.info(f"[ws] connection cleaned up: {client_id}")

