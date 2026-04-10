import json
import asyncio
import time
from typing import Callable, Dict
from fastapi import WebSocket


from core.commons.type_def import TaskInfo


# ============================================================
# WebSocket Connection Manager
# ============================================================

class WebsocketList:
    """
    Manage active websocket connections from AI services.
    Keyed by agent_service_id.
    """

    def __init__(self):
        self.websockets: Dict[str, WebSocket] = {} # dict format: ai_agent_service_id: websocket_instance
        self.lock = asyncio.Lock()

    async def append(self, agent_service_id: str, websocket: WebSocket) -> None:
        async with self.lock:
            self.websockets[agent_service_id] = websocket

    async def get_ws(self, agent_service_id: str) -> WebSocket:
        async with self.lock:
            return self.websockets[agent_service_id]

    async def exist(self, agent_service_id: str) -> bool:
        async with self.lock:
            return agent_service_id in self.websockets

    async def remove(self, agent_service_id: str):
        async with self.lock:
            ws = self.websockets.pop(agent_service_id, None)
            if ws:
                await ws.close()

    async def remove_all(self):
        async with self.lock:
            for ws in self.websockets.values():
                await ws.close()
            self.websockets.clear()

    async def info_ai_task_result(self, task_info: TaskInfo):
        print(f"\n\n[info_ai_task_result] The task_info: {task_info}")
        agent_service_id = task_info.get("ai_service_id")
        
        if not agent_service_id:
            print(f"[info_ai_task_result] Warning: ai_service_id is empty, cannot send websocket message.")
            return

        async with self.lock:
            try:
                websocket = self.websockets.get(agent_service_id)
                if not websocket:
                    print(f"[info_ai_task_result] Warning: websocket not found for ai_service_id={agent_service_id}")
                    return

                resp = {"action": "push_message_to_client"}
                data = {
                    "task_id": task_info.get("task_id"),
                    "client_id": task_info.get("client_id"),
                    "history_id": task_info.get("history_id"),
                    "session_id": task_info.get("session_id"),
                    "messages": {
                        "role": "system",
                        "content": json.dumps(task_info.get("result"))  # 确保发送的是字符串
                    }
                }
                resp["data"] = data

                print(f"\n\n[info_ai_task_result] The following msg will send to ai: {resp}")
                await websocket.send_text(json.dumps(resp))
            except Exception as e:
                print(f"\n\n[info_ai_task_result] Fail: {e}")



# ============================================================
# Action Dispatcher
# ============================================================

class ActionDispatcher:
    """
    Dispatch websocket messages by action name.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, action: str, handler: Callable):
        """
        Register a websocket action handler.

        Args:
            action: Action name in websocket message.
            handler: Async callable (websocket, data).
        """
        self._handlers[action] = handler

    async def dispatch(self, websocket: WebSocket, data: dict):
        action = data.get("action")
        handler = self._handlers.get(action)

        if not handler:
            await websocket.send_text(
                json.dumps(
                    {
                        "action": action,
                        "status": "error",
                        "error": "Undefined action",
                    }
                )
            )
            return

        await handler(websocket, data)


# ============================================================
# WebSocket Message Handler (Memory RPC)
# ============================================================

class WebsocketMessageHandler:
    """
    Handle websocket RPC-style messages for memory service.
    """

    def __init__(self):
        self.dispatcher = ActionDispatcher()

        # ---------- register actions ----------
        self.dispatcher.register("hello", self.hello)
        self.dispatcher.register("ping", self.ping)

    async def handle_message(self, websocket: WebSocket, message: str):
        """
        Entry point for websocket messages.
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            await websocket.send_text(
                json.dumps({"status": "error", "error": "Invalid JSON"})
            )
            return

        await self.dispatcher.dispatch(websocket, data)

    # ---------------------------------------------------------
    # Basic actions
    # ---------------------------------------------------------

    async def hello(self, websocket: WebSocket, data: dict):
        await websocket.send_text("Hello! Welcome to ApiX!")

    async def ping(self, websocket: WebSocket, data: dict):
        await websocket.send_text(
            json.dumps(
                {
                    "action": "pong",
                    "ts": int(time.time()),
                }
            )
        )


# ============================================================
# Instances
# ============================================================

ws_list = WebsocketList()
ws_message_handler = WebsocketMessageHandler()















