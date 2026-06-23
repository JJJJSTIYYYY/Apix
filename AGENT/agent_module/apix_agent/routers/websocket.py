import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import traceback

from apix_agent.commons.type_def import PlatformNotRegister
from apix_agent.apix_event_pipe.stream_event.stream_event_gateway import action_handler
from apix_agent.apix_platform.register import PLATFORM_REGISTRY
from apix_agent.commons.logger import logger
from apix_agent.apix_platform import *


router = APIRouter(tags=["websocket"])

@router.websocket("/ws/{platform}/{client_id}")
async def ws_endpoint(websocket: WebSocket, platform: str, client_id: str):
    await websocket.accept()
    logger.success(f"Client connected: {client_id}")

    try:
        websocket_platform = PLATFORM_REGISTRY[platform]
        if not websocket_platform:
            raise PlatformNotRegister(platform=platform)
        await websocket_platform.register(websocket, client_id)
    except Exception as e:
        logger.error(f"Websocket platform register failed for client {client_id}: {e}")
        await websocket.close()
        return

    try:
        while True:
            raw_data = await websocket.receive_text()
            logger.info(f"Receive data from client {client_id}: {raw_data}")

            try:
                data = json.loads(raw_data)
                data = websocket_platform.trans_payload(data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid json from client {client_id}")
                continue

            action = data.get("action")
            history_id = (data.get("data") or {}).get("history_id")

            # Trigger AI invoke (async / background)

            if action == "chat_with_llm":
                asyncio.create_task(action_handler.chat_with_llm(data))

            elif action == "abort_generation":
                try:
                    await action_handler.abort_generation(data)
                except Exception as e:
                    logger.error(f"Abort generation failed for client {client_id}: {e}")
                    continue

                logger.warning(f"Abort generation by client {client_id} for conversation {history_id}")

            elif action == "resolve_block":
                try:
                    await action_handler.resolve_block(data)
                except Exception as e:
                    logger.error(f"Resolve block failed for client {client_id}: {e}")
                    continue

            else:
                raise ValueError(f"Unknown action: {action}")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {client_id}")

    except Exception as e:
        logger.error(
            "Unexpected error for client="+
            f"{client_id}: {e}\n{traceback.format_exc()}"
        )

    finally:
        await websocket_platform.unregister(client_id)
        logger.info(f"Connection cleaned up: {client_id}")

