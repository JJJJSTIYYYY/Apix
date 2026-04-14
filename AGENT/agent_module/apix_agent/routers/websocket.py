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
            history_id = (data.get("data") or {}).get("history_id")

            # ------------------------------
            # Trigger AI invoke (async / background)
            # ------------------------------

            if action == "chat_with_llm":
                try:
                    generation_id = await websocket_list.create_generation(client_id, history_id)
                except Exception as e:
                    logger.error(f"[ws] create_generation failed client={client_id}: {e}")
                    continue

                logger.info(
                    f"[ws] new generation created: "
                    f"client={client_id}, generation={generation_id}"
                )
                asyncio.create_task(ws_msg_handler.chat_with_llm(generation_id, data))
            elif action == "abort_generation":
                try:
                    generation_id = await websocket_list.create_generation(client_id, history_id, not_active_generation_id=True)
                except Exception as e:
                    logger.error(f"[ws] create_generation failed client={client_id}: {e}")
                    continue

                logger.warning(f"[ws] abort_generation by client={client_id}")
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

