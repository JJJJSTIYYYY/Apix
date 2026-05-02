# import asyncio
# import json
# import traceback
# from typing import Any

# from fastapi import WebSocket

# from apix_agent.apix_platform.platform.platform_base import PlatformBase
# from apix_agent.apix_agent_core.generation_manager import GenerationManager
# from apix_agent.apix_event_pipe.apix_event_gateway import action_handler
# from apix_agent.commons.type_def import ApixEventEnvelope, ApixEntryDataSchema
# from apix_agent.commons.logger import logger


# class QQPlatform(PlatformBase):

#     def __init__(self, gen_mgr: GenerationManager):
#         super().__init__("qq")

#         self.gen_mgr = gen_mgr

#         self._started: bool = False
#         self._queue: asyncio.Queue = asyncio.Queue(maxsize=2048)

#         self._consumer_task: asyncio.Task | None = None

#     # =========================
#     # lifecycle
#     # =========================
#     async def start(self):
#         if self._started:
#             return

#         self._started = True
#         self._consumer_task = asyncio.create_task(self._consumer_loop())

#     async def stop(self):
#         self._started = False

#         if self._consumer_task:
#             self._consumer_task.cancel()
#             await asyncio.gather(self._consumer_task, return_exceptions=True)

#     # =========================
#     # 反向 WS 注册（只有一个）
#     # =========================
#     async def attach_websocket(self, websocket: WebSocket):
#         """
#         OneBot 反向 WebSocket 接入点
#         """
#         await websocket.accept()
#         logger.success("[QQPlatform] OneBot WS connected")

#         try:
#             while True:
#                 raw = await websocket.receive_text()

#                 try:
#                     data = json.loads(raw)
#                 except Exception:
#                     logger.error("[QQPlatform] invalid json")
#                     continue

#                 # 入队（不要阻塞）
#                 try:
#                     self._queue.put_nowait(data)
#                 except asyncio.QueueFull:
#                     logger.warning("[QQPlatform] queue full, drop event")

#         except Exception:
#             logger.error(f"[QQPlatform] ws error:\n{traceback.format_exc()}")

#         finally:
#             logger.warning("[QQPlatform] WS disconnected")

#     # =========================
#     # consumer 核心逻辑
#     # =========================
#     async def _consumer_loop(self):
#         while True:
#             try:
#                 raw_data = await self._queue.get()

#                 data = self.trans_payload(raw_data)

#                 action = data.get("action")
#                 target = data.get("target") or {}
#                 client_id = target.get("id")
#                 history_id = (data.get("data") or {}).get("history_id")

#                 # ====== 复用你原来的逻辑 ======
#                 if action == "chat_with_llm":
#                     try:
#                         generation_id = await self.gen_mgr.create_generation(
#                             client_id, history_id
#                         )
#                     except Exception as e:
#                         logger.error(f"[QQPlatform] create_generation failed: {e}")
#                         continue

#                     asyncio.create_task(
#                         action_handler.chat_with_llm(generation_id, data)
#                     )

#                 elif action == "abort_generation":
#                     try:
#                         await self.gen_mgr.abort_by_history_id(client_id, history_id)
#                     except Exception as e:
#                         logger.error(f"[QQPlatform] abort failed: {e}")

#                 else:
#                     logger.warning(f"[QQPlatform] unknown action: {action}")

#             except asyncio.CancelledError:
#                 break

#             except Exception:
#                 logger.error(f"[QQPlatform] consumer error:\n{traceback.format_exc()}")

#     # =========================
#     # outbound（调用 OneBot API）
#     # =========================
#     async def send(self, client_id: str, envelope: ApixEventEnvelope):
#         """
#         这里你后面可以接 http api 或 ws send
#         """
#         pass

#     # =========================
#     # OneBot -> 统一结构
#     # =========================
#     def trans_payload(self, raw_data: Any) -> ApixEntryDataSchema:

#         post_type = raw_data.get("post_type")

#         if post_type == "message":
#             msg_type = raw_data.get("message_type")

#             if msg_type == "private":
#                 return {
#                     "action": "chat_with_llm",
#                     "target": {
#                         "id": str(raw_data.get("user_id")),
#                         "platform": "qq"
#                     },
#                     "data": {
#                         "messages": raw_data.get("message"),
#                         "history_id": str(raw_data.get("user_id"))
#                     }
#                 }

#             if msg_type == "group":
#                 return {
#                     "action": "chat_with_llm",
#                     "target": {
#                         "id": str(raw_data.get("user_id")),
#                         "group_id": str(raw_data.get("group_id")),
#                         "platform": "qq"
#                     },
#                     "data": {
#                         "messages": raw_data.get("message"),
#                         "history_id": str(raw_data.get("group_id"))
#                     }
#                 }

#         return {
#             "action": "unknown",
#             "target": {
#                 "platform": "qq"
#             },
#             "data": raw_data
#         }

#     # =========================
#     # outbound envelope convert（预留）
#     # =========================
#     def _open_envelope(self, envelope: ApixEventEnvelope) -> dict:
#         return {}