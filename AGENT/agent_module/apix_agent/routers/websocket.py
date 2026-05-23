import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import traceback

from apix_agent.commons.type_def import PlatformNotRegister
from apix_agent.apix_agent_core.generation_manager import generation_manager
from apix_agent.apix_event_pipe.apix_event_gateway import action_handler
from apix_agent.apix_platform.register import PLATFORM_REGISTRY
from apix_agent.commons.logger import logger
from apix_agent.apix_platform import *


router = APIRouter(tags=["websocket"])

@router.websocket("/ws/{platform}/{client_id}")
async def ws_endpoint(websocket: WebSocket, platform: str, client_id: str):
    await websocket.accept()
    logger.success(f"[ws] client connected: {client_id}")

    try:
        websocket_platform = PLATFORM_REGISTRY[platform]
        if not websocket_platform:
            raise PlatformNotRegister(platform=platform)
        await websocket_platform.register(websocket, client_id)
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
                data = websocket_platform.trans_payload(data)
            except json.JSONDecodeError as e:
                logger.error(f"[ws] invalid json from client={client_id}")
                continue

            action = data.get("action")
            history_id = (data.get("data") or {}).get("history_id")

            # Trigger AI invoke (async / background)

            if action == "chat_with_llm":
                try:
                    generation_id = await generation_manager.create_generation(client_id, history_id, platform)
                except Exception as e:
                    logger.error(f"[ws] create_generation failed client={client_id}: {e}")
                    continue

                logger.info(
                    f"[ws] new generation created: "
                    f"client={client_id}, generation={generation_id}"
                )
                asyncio.create_task(action_handler.chat_with_llm(generation_id, data))

            elif action == "abort_generation":
                try:
                    await generation_manager.abort_by_history_id(client_id, history_id, platform)
                except Exception as e:
                    logger.error(f"[ws] abort_generation failed client={client_id}: {e}")
                    continue

                logger.warning(f"[ws] abort_generation by client={client_id}, history={history_id}")

            elif action == "resolve_block":
                try:
                    await action_handler.resolve_block(data)
                except Exception as e:
                    logger.error(f"[ws] resolve_block failed client={client_id}: {e}")
                    continue

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
        await websocket_platform.unregister(client_id)
        logger.info(f"[ws] connection cleaned up: {client_id}")

