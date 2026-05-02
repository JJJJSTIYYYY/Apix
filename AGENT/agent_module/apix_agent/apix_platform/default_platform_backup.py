# import asyncio
# from dataclasses import dataclass, field
# from typing import Any, Dict, Optional, cast

# from fastapi import WebSocket

# from apix_agent.commons.auto_init import auto_init
# from apix_agent.apix_platform.platform_base import PlatformBase
# from apix_agent.apix_event_pipe.apix_event_gateway import generation_manager, GenerationManager
# from apix_agent.apix_platform.register import register_platform
# from apix_agent.commons.type_def import ApixEntryDataSchema, ApixEventEnvelope
# from apix_agent.commons.logger import logger


# # User Context
# @dataclass
# class UserSocketContext:
#     websocket: WebSocket
#     client_id: str

#     # Message queue for this client.
#     queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=1024))

#     connected: bool = True
#     # Background sender task for this client.
#     sender_task: Optional[asyncio.Task] = None

#     ctx_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# class DefaultPlatform(PlatformBase):

#     def __init__(self, gen_mgr: GenerationManager):
#         super().__init__("default")

#         self._connections: Dict[str, UserSocketContext] = {}
#         self._started: bool = False
#         self.gen_mgr = gen_mgr

#     # lifecycle
#     async def start(self):
#         if self._started:
#             return

#         self._started = True

#         for ctx in self._connections.values():
#             if ctx.sender_task is None or ctx.sender_task.done():
#                 ctx.sender_task = asyncio.create_task(self._sender_loop(ctx))

#     async def stop(self):
#         self._started = False

#         tasks = []
#         for ctx in self._connections.values():
#             if ctx.sender_task:
#                 ctx.sender_task.cancel()
#                 tasks.append(ctx.sender_task)

#         if tasks:
#             await asyncio.gather(*tasks, return_exceptions=True)

#         for ctx in self._connections.values():
#             ctx.sender_task = None

#     # connection management
#     async def register(self, websocket: WebSocket, client_id: str):
#         old_ctx = self._connections.get(client_id)

#         if old_ctx:
#             old_ctx.websocket = websocket
#             old_ctx.connected = True

#             if old_ctx.sender_task:
#                 old_ctx.sender_task.cancel()
#                 await asyncio.gather(old_ctx.sender_task, return_exceptions=True)

#             old_ctx.sender_task = asyncio.create_task(self._sender_loop(old_ctx))
#             return

#         ctx = UserSocketContext(websocket=websocket, client_id=client_id)
#         self._connections[client_id] = ctx

#         if self._started:
#             ctx.sender_task = asyncio.create_task(self._sender_loop(ctx))

#     async def unregister(self, client_id: str):
#         ctx = self._connections.get(client_id)
#         if not ctx:
#             return

#         ctx.connected = False

#         if ctx.sender_task:
#             ctx.sender_task.cancel()
#             await asyncio.gather(ctx.sender_task, return_exceptions=True)

#     def _get_ctx(self, client_id: str) -> UserSocketContext:
#         ctx = self._connections.get(client_id)
#         if not ctx:
#             raise RuntimeError(f"WebSocket not registered, client id: {client_id}")
#         return ctx

#     # envelope convert
#     def _open_envelope(self, envelope: ApixEventEnvelope) -> dict:
#         """
#         Convert ApixEventEnvelope -> legacy websocket payload

#         Keep compatibility with old frontend protocol.
#         """

#         if not envelope:
#             return {}

#         target = envelope.get("target") or {}
#         data = envelope.get("data") or {}

#         event = envelope.get("event")
#         generation_id = envelope.get("generation_id")
#         ts = envelope.get("timestamp")

#         client_id = target.get("id")
#         platform = target.get("platform", "default")
#         history_id = target.get("conversation_id", "")

#         return {
#             "action": event,
#             "ts": int(ts * 1000) if ts else 0,
#             "generation_id": generation_id,
#             "client_id": client_id,
#             "platform": platform,
#             "data": {
#                 "history_id": history_id,
#                 "messages": data
#             }
#         }

#     # sender loop
#     async def _sender_loop(self, ctx: UserSocketContext):
#         try:
#             while True:
#                 envelope: ApixEventEnvelope = await ctx.queue.get()
#                 data = self._open_envelope(envelope)

#                 try:
#                     await ctx.websocket.send_json(data)
#                 except Exception:
#                     logger.warning("websocket send failed - disconnected")
#                     ctx.connected = False
#                     break

#         except asyncio.CancelledError:
#             ctx.connected = False
#             logger.info(f"[sender_loop] cancelled for client={ctx.client_id}")

#     # interface
#     async def send(self, client_id: str, envelope: ApixEventEnvelope):
#         """
#         PlatformBase override

#         Directly enqueue event to websocket queue.
#         """
#         await self.enqueue_event(envelope)


#     def trans_payload(self, raw_data: Any) -> ApixEntryDataSchema:
#         return cast(ApixEntryDataSchema, raw_data)


#     async def enqueue_event(self, envelope: ApixEventEnvelope):
#         target = envelope.get("target") or {}
#         client_id = target.get("id")

#         if not client_id:
#             return

#         ctx = self._connections.get(client_id)
#         if not ctx:
#             return

#         await ctx.queue.put(envelope)

# websocket_platform = DefaultPlatform(generation_manager)


# @auto_init.auto_start
# async def start_websocket():
#     await websocket_platform.start()


# @auto_init.auto_stop
# async def stop_websocket():
#     await websocket_platform.stop()


# register_platform(websocket_platform)