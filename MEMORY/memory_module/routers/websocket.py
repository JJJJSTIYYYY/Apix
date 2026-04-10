import base64
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from core.websocket.websocket_manager import ws_list, ws_message_handler


router = APIRouter(tags=["websocket"])

@router.websocket("/ws/{ai_service_id}")
async def ws_endpoint(ai_service_id: str, websocket: WebSocket):
    if await ws_list.exist(websocket):
        # Connection has existed, refuse and close
        await websocket.close(code=4000)
        return
    await ws_list.append(ai_service_id, websocket)
    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_text()
            await ws_message_handler.handle_message(websocket, message)
            # await websocket.send_text(message)

    except WebSocketDisconnect:
        print(f'{websocket}: Connection close')
        await ws_list.remove(websocket)