# import asyncio
# import copy
# import time
# import traceback
# from dataclasses import dataclass, field
# from typing import Dict, Literal, Optional
# from uuid import uuid4

# from fastapi import WebSocket

# from apix_agent.commons.resource_cleaner import resource_cleaner
# from apix_agent.commons.logger import logger
# from apix_agent.apix_agent_core.agent import ai_agent
# from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
# from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox
# from apix_agent.commons.type_def import MainAgentState, MinimalEnvelopeData, ApixEventEnvelope
# from apix_agent.global_config import GENERATION_TTL


# # =========================
# # Generation State
# # =========================
# @dataclass
# class GenerationState:
#     """
#     State for a single AI generation.
#     """

#     history_id: str
#     generation_id: str
#     client_id: str

#     # running / finished / aborted
#     status: Literal["running", "finished", "aborted"] = "running"

#     cache_tokens: dict = field(default_factory=lambda: {
#         "role": "ai",
#         "content": "",
#         "think": "",
#         "extra": {},
#         "info": {},
#         "generation_id": "",
#         "timestamp": 0
#     })
#     parent_node_id: str = field(default='-')

#     created_at: float = field(default_factory=time.time)

#     # Protect cache_tokens concurrent access
#     gen_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# # =========================
# # Generation Manager
# # =========================
# class GenerationManager:
#     """
#     Manage generation lifecycle independently from websocket transport.
#     """

#     def __init__(self):
#         self._connections: Dict[str, Dict[str, GenerationState]] = {}
#         self._active_generation_ids: Dict[str, list[str]] = {}
#         self._locks: Dict[str, asyncio.Lock] = {}

#     def _get_lock(self, client_id: str) -> asyncio.Lock:
#         lock = self._locks.get(client_id)
#         if not lock:
#             lock = asyncio.Lock()
#             self._locks[client_id] = lock
#         return lock

#     def _get_client_generations(self, client_id: str) -> Dict[str, GenerationState]:
#         gens = self._connections.get(client_id)
#         if gens is None:
#             gens = {}
#             self._connections[client_id] = gens
#         return gens

#     def _get_active_list(self, client_id: str) -> list[str]:
#         active_list = self._active_generation_ids.get(client_id)
#         if active_list is None:
#             active_list = []
#             self._active_generation_ids[client_id] = active_list
#         return active_list

#     async def create_generation(
#         self,
#         client_id: str,
#         history_id: str,
#         *,
#         append_cache_memory: bool = True,
#         not_active_generation_id=False
#     ) -> str:
#         logger.warning("\n############################################\n            NEW GENERATION START\n############################################\n")

#         new_gen_id = str(uuid4())

#         async with self._get_lock(client_id):
#             gens = self._get_client_generations(client_id)
#             active_generation_ids = self._get_active_list(client_id)

#             old_gen = None
#             for gid in active_generation_ids:
#                 gen = gens.get(gid)
#                 if gen and gen.history_id == history_id and gen.status == "running":
#                     old_gen = gen
#                     break

#             if old_gen:
#                 old_gen.status = "aborted"

#             gens[new_gen_id] = GenerationState(
#                 history_id=history_id,
#                 generation_id=new_gen_id,
#                 client_id=client_id
#             )
#             if not not_active_generation_id:
#                 active_generation_ids.append(new_gen_id)

#         if old_gen and append_cache_memory and old_gen.status == "aborted":
#             async with old_gen.gen_lock:
#                 interrupted_msg = copy.deepcopy(old_gen.cache_tokens)

#             if interrupted_msg:
#                 ts = int(time.time() * 1000)

#                 content = interrupted_msg.get("content", "")
#                 think = interrupted_msg.get("think", "")

#                 think_endswith = "[Conversation Abort]" if think and not content else ""
#                 content_endswith = "[Conversation Abort]" if content or not think_endswith else ""

#                 interrupted_msg.update({
#                     "content": content + content_endswith,
#                     "think": think + think_endswith,
#                     "generation_id": old_gen.generation_id,
#                     "timestamp": ts,
#                 })

#                 parent_node_id = old_gen.parent_node_id
#                 if parent_node_id and parent_node_id != '-':
#                     await ai_context_manager.append_to_messages(
#                         client_id,
#                         history_id,
#                         interrupted_msg,
#                         parent_node_id
#                     )
#                     logger.warning("[create_generation] Append [Conversation Abort] mark to database.")
#                 else:
#                     logger.warning("[create_generation] Not allow to [Conversation Abort] mark to database as a root node.")

#         return new_gen_id

#     def abort_generation(self, client_id: str, generation_id: str):
#         gens = self._connections.get(client_id)
#         if not gens:
#             return

#         gen = gens.get(generation_id)
#         if not gen:
#             return

#         gen.status = "aborted"

#         active_generation_ids = self._active_generation_ids.get(client_id)
#         if active_generation_ids:
#             try:
#                 active_generation_ids.remove(generation_id)
#             except ValueError:
#                 pass

#     def is_generation_aborted(self, client_id: str, generation_id: str) -> bool:
#         gens = self._connections.get(client_id)
#         if not gens:
#             return True

#         gen = gens.get(generation_id)
#         return (not gen) or gen.status != "running"

#     def get_generation(self, client_id: str, generation_id: str) -> Optional[GenerationState]:
#         gens = self._connections.get(client_id)
#         if not gens:
#             return None
#         return gens.get(generation_id)

#     async def clean_expired(self) -> int:
#         """
#         Clean expired generations across all clients.

#         Returns:
#             Total number of removed generations

#         Behavior:
#             - Removes finished/aborted generations older than TTL
#             - Safe to call periodically by external scheduler
#         """
#         if not self._connections:
#             return 0

#         now = time.time()
#         total_removed = 0

#         for client_id, gens in list(self._connections.items()):
#             if not gens:
#                 continue

#             async with self._get_lock(client_id):
#                 to_delete = []

#                 for gen_id, gen in gens.items():
#                     if gen.status == "running":
#                         continue

#                     age = now - gen.created_at
#                     if age > GENERATION_TTL:
#                         to_delete.append(gen_id)

#                 for gen_id in to_delete:
#                     gens.pop(gen_id, None)

#                     active_generation_ids = self._active_generation_ids.get(client_id, [])
#                     try:
#                         active_generation_ids.remove(gen_id)
#                     except ValueError:
#                         pass

#                 if to_delete:
#                     removed = len(to_delete)
#                     total_removed += removed
#                     logger.info(f"[generation_cache] client={client_id}, removed={removed} generation(s)")

#         return total_removed


# # =========================
# # User Context
# # =========================
# @dataclass
# class UserSocketContext:
#     websocket: WebSocket
#     client_id: str

#     active_generation_ids: list[str] = field(default_factory=list)
#     generations: Dict[str, GenerationState] = field(default_factory=dict)

#     # Message queue for this client.
#     queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=1024))

#     # Background sender task for this client.
#     sender_task: Optional[asyncio.Task] = None

#     ctx_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# # =========================
# # Websocket Manager
# # =========================
# class WebsocketList:

#     def __init__(self):
#         self._connections: Dict[str, UserSocketContext] = {}
#         self._started: bool = False

#     async def start(self):
#         """
#         Start background sender tasks for all existing connections.
#         This should be called explicitly from FastAPI lifespan.
#         """
#         self._started = True

#         for ctx in self._connections.values():
#             if ctx.sender_task is None or ctx.sender_task.done():
#                 ctx.sender_task = asyncio.create_task(self._sender_loop(ctx))

#     async def stop(self):
#         """
#         Stop all background sender tasks.
#         This should be called explicitly from FastAPI lifespan shutdown.
#         """
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

#     async def register(self, websocket: WebSocket, client_id: str):
#         old_ctx = self._connections.get(client_id)
#         if old_ctx:
#             for gen in old_ctx.generations.values():
#                 gen.status = "aborted"

#             if old_ctx.sender_task:
#                 old_ctx.sender_task.cancel()
#                 await asyncio.gather(old_ctx.sender_task, return_exceptions=True)

#         ctx = UserSocketContext(
#             websocket=websocket,
#             client_id=client_id,
#         )

#         self._connections[client_id] = ctx

#         if self._started:
#             ctx.sender_task = asyncio.create_task(self._sender_loop(ctx))

#     def unregister(self, client_id: str):
#         ctx = self._connections.pop(client_id, None)
#         if not ctx:
#             return

#         for gen in ctx.generations.values():
#             gen.status = "aborted"

#         if ctx.sender_task:
#             ctx.sender_task.cancel()

#         ctx.generations.clear()
#         ctx.active_generation_ids = []

#     def _get_ctx(self, client_id: str) -> UserSocketContext:
#         ctx = self._connections.get(client_id)
#         if not ctx:
#             raise RuntimeError(f"WebSocket not registered, client id: {client_id}")
#         return ctx
    
#     def _open

#     async def _sender_loop(self, ctx: UserSocketContext):
#         """
#         Background sender loop:
#         - Consume ApixEventEnvelope from queue
#         - Send it to the websocket as JSON
#         """
#         try:
#             while True:
#                 envelope: ApixEventEnvelope = await ctx.queue.get()
#                 try:

#                     await ctx.websocket.send_json(envelope)
#                 except Exception:
#                     logger.warning("websocket send failed")
#         except asyncio.CancelledError:
#             logger.info(f"[sender_loop] cancelled for client={ctx.client_id}")

#     async def enqueue_event(self, envelope: ApixEventEnvelope):
#         """
#         Enqueue one ApixEventEnvelope for the target client.
#         """
#         target = envelope.get("target") or {}
#         client_id = target.get("id")

#         if not client_id:
#             return

#         ctx = self._connections.get(client_id)
#         if not ctx:
#             return

#         await ctx.queue.put(envelope)


# # =========================
# # Handler
# # =========================
# class WebsocketMessageHandler:

#     def __init__(self, ws_lst: WebsocketList, gen_mgr: GenerationManager):
#         self.ws_list = ws_lst
#         self.gen_mgr = gen_mgr

#     def _build_envelope(
#         self,
#         event: str,
#         client_id: str,
#         platform: str,
#         data: MinimalEnvelopeData,
#         trace_id: str,
#     ) -> ApixEventEnvelope:
#         return {
#             "event": event,
#             "target": {
#                 "id": client_id,
#                 "platform": platform,
#             },
#             "data": data,
#             "trace_id": trace_id,
#             "timestamp": time.time(),
#         }

#     async def chat_with_llm(self, generation_id, payload: dict):
#         logger.trace('[WebsocketMessageHandler] chat_with_llm Enter')

#         client_id = None
#         history_id = None
#         agent = None
#         work_dir = ''

#         try:
#             data = payload.get("data") or {}
#             client_id = data.get("client_id")
#             session_id = data.get("session_id", "")
#             history_id = data.get("history_id")
#             platform = data.get("platform", "default")
#             message = data.get("messages", {})
#             re_generate = data.get("re_generate", False)
#             config = data.get("config", {})
#             work_dir = config.get("work_dir", "")

#             enable_agent_assign = bool(config.get("enable_agent_assign", False))
#             enable_agent_swarm = bool(config.get("enable_agent_swarm", False))
#             agent_role = "agent"
#             if enable_agent_assign:
#                 agent_role = "main_agent"
#             if enable_agent_swarm:
#                 agent_role = "team_leader"

#             if not isinstance(message, dict):
#                 class_name = type(message).__name__
#                 raise ValueError(f"[chat_with_llm] Unexpected data type: message is {class_name}, expected dict.")

#             timestamp = int(time.time() * 1000)
#             initial_state: MainAgentState = {
#                 "agent_name": "APIX",
#                 "agent_role": agent_role,
#                 "client_id": client_id,
#                 "session_id": session_id,
#                 "history_id": history_id,
#                 "node_id": generation_id[-12:] + "-apix",
#                 "platform": platform,
#                 "generation_id": generation_id,
#                 "config": config,
#                 "timestamp": timestamp,
#                 "input": message,
#                 "re_generate": re_generate,
#                 "messages": [],
#                 "current_tool_calls": [],
#                 "longterm_memory": None,
#                 "shortterm_memory": "",
#                 "rule_prompt": None,
#                 "runtime_prompt": None,
#                 "llm_calls": 0,
#                 "sandbox": '',
#                 "todos": [],
#                 "memorandum": [],
#                 "skills": [],
#                 "loaded_skills_cache": [],
#                 "documents": [],
#                 "llm_retry_count": 0,
#                 "context_compress_level": 0,
#                 "context_fold_split_mark": [],
#                 "error": "",
#                 "error_detail": "",
#             }

#             agent = await ai_agent.submit_agent_task(agent_role, "APIX", config)
#             astream = agent.astream(initial_state, {"recursion_limit": 1024}, stream_mode="custom")

#             async for achunk in astream:
#                 # achunk is already an ApixEventEnvelope.
#                 chunk_event = achunk.get("data") or {}
#                 action = chunk_event.get("event_name")

#                 if action == 'parent_id_return':
#                     content = chunk_event.get("content")
#                     gen = self.gen_mgr.get_generation(client_id, generation_id)
#                     if gen:
#                         gen.parent_node_id = content

#                     # Getting the parent node id means a agent stream start.
#                     await self.ws_list.enqueue_event(
#                         self._build_envelope(
#                             event="msg_stream_start",
#                             client_id=client_id,
#                             platform=platform,
#                             data={
#                                 "event_name": "msg_stream_start",
#                                 "content": {
#                                     "node_id": generation_id[-12:] + "-apix",
#                                     "parent_id": content
#                                 }
#                             },
#                             trace_id=generation_id,
#                         )
#                     )

#                 if self.gen_mgr.is_generation_aborted(client_id, generation_id):
#                     await astream.aclose()
#                     await self.ws_list.enqueue_event(
#                         self._build_envelope(
#                             event="msg_stream_abort",
#                             client_id=client_id,
#                             platform=platform,
#                             data={
#                                 "event_name": "user_interrupt",
#                                 "content": ""
#                             },
#                             trace_id=generation_id,
#                         )
#                     )
#                     logger.warning(f"[chat_with_llm] this generation has been aborted, generation_id = {generation_id}")
#                     return

#                 await self.ws_list.enqueue_event(achunk)
#                 await asyncio.sleep(0.06)

#             await self.ws_list.enqueue_event(
#                 self._build_envelope(
#                     event="msg_stream_end",
#                     client_id=client_id,
#                     platform=platform,
#                     data={
#                         "event_name": "msg_stream_end",
#                         "content": None
#                     },
#                     trace_id=generation_id,
#                 )
#             )

#         except Exception as e:
#             logger.error(f"[chat_with_llm error] {client_id}: {traceback.format_exc()}")

#             if client_id:
#                 self.gen_mgr.abort_generation(client_id, generation_id)

#             await self.ws_list.enqueue_event(
#                 self._build_envelope(
#                     event="msg_stream_abort",
#                     client_id=client_id,
#                     platform=platform if 'platform' in locals() else 'default',
#                     data={
#                         "event_name": "error_occurred",
#                         "content": f"{e.__class__.__name__}: {str(e)}"
#                     },
#                     trace_id=generation_id,
#                 )
#             )

#         finally:
#             await ai_agent.done(agent)
#             await agent_sandbox.done(client_id=client_id, conversation_id=history_id, work_dir=work_dir)


# websocket_list = WebsocketList()
# generation_manager = GenerationManager()
# ws_msg_handler = WebsocketMessageHandler(websocket_list, generation_manager)


# @resource_cleaner.auto_clear
# async def clean_ws():
#     return await generation_manager.clean_expired()