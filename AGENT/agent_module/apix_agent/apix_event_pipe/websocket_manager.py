import asyncio
import copy
import time
from dataclasses import dataclass, field
from typing import Dict, Literal
from uuid import uuid4
from fastapi import WebSocket
import traceback

from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.agent import ai_agent
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.commons.type_def import MainAgentState, MinimalEnvelopeData
from apix_agent.global_config import GENERATION_TTL_SECONDS
from apix_agent.commons.type_def import ApixEventEnvelope


# =========================
# Generation State
# =========================
@dataclass
class GenerationState:
    """
    State for a single AI generation.
    """

    history_id: str
    generation_id: str
    client_id: str

    # running / finished / aborted
    status: Literal["running", "finished", "aborted"] = "running"

    cache_tokens: dict = field(default_factory=lambda: {
        "role": "ai",
        "content": "",
        "think": "",
        "extra": {},
        "info": {},
        "generation_id": "",
        "timestamp": 0
    })

    created_at: float = field(default_factory=time.time)

    # Protect cache_tokens concurrent access
    gen_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# =========================
# User Context
# =========================
@dataclass
class UserSocketContext:
    websocket: WebSocket
    client_id: str

    active_generation_ids: list[str] = field(default_factory=list)
    generations: Dict[str, GenerationState] = field(default_factory=dict)

    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ctx_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# =========================
# Websocket Manager
# =========================
class WebsocketList:

    def __init__(self):
        self._connections: Dict[str, UserSocketContext] = {}

        self._ttl_seconds = GENERATION_TTL_SECONDS
        self._cleanup_interval = 30  # run every 30s
        self._cleanup_task = None

    async def start(self):
        """
        Start background cleanup task.
        Must be called after event loop is running (e.g. FastAPI lifespan).
        """
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("[WebsocketList] cleanup task started")

    async def stop(self):
        """
        Gracefully stop background cleanup task.
        """
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("[WebsocketList] cleanup task stopped")

    async def register(self, websocket: WebSocket, client_id: str):
        old_ctx = self._connections.get(client_id)
        if old_ctx:
            for gen in old_ctx.generations.values():
                gen.status = "aborted"

        self._connections[client_id] = UserSocketContext(
            websocket=websocket,
            client_id=client_id,
        )

    def unregister(self, client_id: str):
        ctx = self._connections.pop(client_id, None)
        if not ctx:
            return

        for gen in ctx.generations.values():
            gen.status = "aborted"

        ctx.generations.clear()
        ctx.active_generation_ids = []

    def _get_ctx(self, client_id: str) -> UserSocketContext:
        ctx = self._connections.get(client_id)
        if not ctx:
            raise RuntimeError(f"WebSocket not registered, client id: {client_id}")
        return ctx

    async def create_generation(self, client_id: str, history_id: str, *, append_cache_memory: bool = True, not_active_generation_id = False) -> str:
        ctx = self._get_ctx(client_id)
        new_gen_id = str(uuid4())

        async with ctx.ctx_lock:
            old_gen = None

            for gid in ctx.active_generation_ids:
                gen = ctx.generations.get(gid)
                if gen and gen.history_id == history_id and gen.status == "running":
                    old_gen = gen
                    break

            if old_gen:
                old_gen.status = "aborted"

            ctx.generations[new_gen_id] = GenerationState(
                history_id=history_id,
                generation_id=new_gen_id,
                client_id=client_id
            )
            if not not_active_generation_id: ctx.active_generation_ids.append(new_gen_id)

        if old_gen and append_cache_memory and old_gen.status == "aborted":
            async with old_gen.gen_lock:
                interrupted_msg = copy.deepcopy(old_gen.cache_tokens)

            if interrupted_msg:
                ts = int(time.time() * 1000)

                content = interrupted_msg.get("content", "")
                think = interrupted_msg.get("think", "")

                think_endswith = "[Conversation Abort]" if think and not content else ""
                content_endswith = "[Conversation Abort]" if content or not think_endswith else ""

                interrupted_msg.update({
                    "content": content + content_endswith,
                    "think": think + think_endswith,
                    "generation_id": old_gen.generation_id,
                    "timestamp": ts,
                })

                await ai_context_manager.append_to_messages(
                    client_id,
                    history_id,
                    interrupted_msg
                )
                logger.warning("[create_generation] Append [Conversation Abort] mark to database.")

        return new_gen_id

    def abort_generation(self, client_id: str, generation_id: str):
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        if not gen:
            return

        gen.status = "aborted"

        try:
            ctx.active_generation_ids.remove(generation_id)
        except ValueError:
            pass

    def is_generation_aborted(self, client_id: str, generation_id: str) -> bool:
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        return (not gen) or gen.status != "running"
    
    async def _cleanup_loop(self):
        """
        Background task: periodically cleanup expired generations.
        """
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired_generations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[cleanup_loop error] {e}")

    async def _cleanup_expired_generations(self):
        """
        Remove finished/aborted generations after TTL.
        """
        if not self._connections:
            return

        now = time.time()

        for client_id, ctx in list(self._connections.items()):
            async with ctx.ctx_lock:

                to_delete = []

                for gen_id, gen in ctx.generations.items():
                    if gen.status == "running":
                        continue

                    age = now - gen.created_at

                    if age > self._ttl_seconds:
                        to_delete.append(gen_id)

                for gen_id in to_delete:
                    ctx.generations.pop(gen_id, None)

                    try:
                        ctx.active_generation_ids.remove(gen_id)
                    except ValueError:
                        pass

                if to_delete:
                    logger.debug(
                        f"[cleanup] client={client_id}, removed={len(to_delete)} generations"
                    )

    # =========================
    # Send helpers
    # =========================
    async def _safe_send(self, ctx: UserSocketContext, payload: dict):
        try:
            async with ctx.send_lock:
                await ctx.websocket.send_json(payload)
        except Exception:
            logger.warning("websocket send failed")

    async def send_ai_stream_token(self, generation_id, client_id, history_id, delta: ApixEventEnvelope):
        target = delta.get("target")
        client_id = target.get("id") # Refresh client_id
        platform = target.get("platform")

        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)

        if not gen or gen.status != "running":
            return

        delta_data = delta.get("data")
        action = delta_data.get("event_name")
        content = delta_data.get("content")
        async with gen.gen_lock:
            if action == "node_stream_start":
                gen.cache_tokens = {
                    "role": "ai",
                    "content": "",
                    "think": "",
                    "extra": {},
                    "info": {},
                    "generation_id": "",
                    "timestamp": 0
                }
            elif action == "messages_persist_end":
                gen.cache_tokens["content"] = ""
                gen.cache_tokens["think"] = ""

            elif action == "content_chunk_rtn":
                gen.cache_tokens["content"] += content
            elif action == "think_chunk_rtn":
                gen.cache_tokens["think"] += content
            elif action == "tool_exec_chunk_rtn":
                gen.cache_tokens["content"] = ""
                gen.cache_tokens["think"] = ""

        payload = {
            "action": action,
            "ts": int(time.time() * 1000),
            "generation_id": generation_id,
            "client_id": client_id,
            "platform": platform,
            "data": {
                "history_id": history_id,
                "messages": delta_data,
            },
        }

        await self._safe_send(ctx, payload)

    async def send_ai_stream_start(self, generation_id, client_id, history_id, platform='default'):
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        if not gen or gen.status != "running":
            return

        event: MinimalEnvelopeData = {
            "event_name": "msg_stream_start",
            "content": None
        }

        payload = {
            "action": "msg_stream_start",
            "ts": int(time.time() * 1000),
            "generation_id": generation_id,
            "client_id": client_id,
            "platform": platform,
            "data": {
                "history_id": history_id,
                "messages": event
            },
        }

        await self._safe_send(ctx, payload)

    async def send_ai_stream_end(self, generation_id, client_id, history_id, platform='default'):
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        if not gen or gen.status != "running":
            return

        event: MinimalEnvelopeData = {
            "event_name": "msg_stream_end",
            "content": None
        }

        payload = {
            "action": "msg_stream_end",
            "ts": int(time.time() * 1000),
            "generation_id": generation_id,
            "client_id": client_id,
            "platform": platform,
            "data": {
                "history_id": history_id,
                "messages": event
            },
        }

        await self._safe_send(ctx, payload)

        gen.status = "finished"

        try:
            ctx.active_generation_ids.remove(generation_id)
        except ValueError:
            pass

    async def send_ai_stream_abort(
            self, 
            generation_id, 
            client_id, 
            history_id, 
            platform = 'default', 
            reason: Literal["user_interrupt", "error_occurred"] = "user_interrupt", 
            content = ""
        ):
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        if not gen:
            return
        
        event: MinimalEnvelopeData = {
            "event_name": reason,
            "content": content
        }

        payload = {
            "action": "msg_stream_abort",
            "ts": int(time.time() * 1000),
            "generation_id": generation_id,
            "client_id": client_id,
            "platform": platform,
            "data": {
                "history_id": history_id,
                "messages": event,
            },
        }

        await self._safe_send(ctx, payload)



# =========================
# Handler
# =========================
class WebsocketMessageHandler:

    def __init__(self, ws_lst: WebsocketList):
        self.ws_list = ws_lst

    async def chat_with_llm(self, generation_id, payload: dict):
        logger.trace('[WebsocketMessageHandler] chat_with_llm Enter')

        client_id = None
        history_id = None

        try:
            data = payload.get("data") or {}
            client_id = data.get("client_id")
            session_id = data.get("session_id", "")
            history_id = data.get("history_id")
            platform = data.get("platform", "default")
            message = data.get("messages", {})
            config = data.get("config", {})
            
            enable_agent_assign = bool(config.get("enable_agent_assign", False))
            enable_agent_swarm = bool(config.get("enable_agent_swarm", False))
            agent_role = "agent"
            if enable_agent_assign:
                agent_role = "main_agent"
            if enable_agent_swarm:
                agent_role = "team_leader"

            if not isinstance(message, dict):
                class_name = type(message).__name__
                raise ValueError(f"[chat_with_llm] Unexpected data type: message is {class_name}, expected dict.")

            timestamp = int(time.time() * 1000)
            initial_state: MainAgentState = {
                "agent_name": "APIX",
                "agent_role": agent_role,
                "client_id": client_id,
                "session_id": session_id,
                "history_id": history_id,
                "platform": platform,
                "generation_id": generation_id,
                "config": config,
                "timestamp": timestamp,
                "input": message,
                "messages": [],
                "current_tool_calls": [],
                "longterm_memory": None,
                "shortterm_memory": "",
                "rule_prompt": None,
                "runtime_prompt": None,
                "llm_calls": 0,
                "sandbox": '',
                "todos": [],
                "memorandum": [],
                "skills": [],
                "loaded_skills_cache": [],
                "documents": [],
                "llm_retry_count": 0,
                "context_compress_level": 0,
                "context_fold_split_mark": [],
                "error": "",
            }

            astream = await ai_agent.submit_agent_task(initial_state, config, "MAIN")

            await self.ws_list.send_ai_stream_start(generation_id, client_id, history_id)

            async for achunk in astream:
                if self.ws_list.is_generation_aborted(client_id, generation_id):
                    await astream.aclose()
                    await self.ws_list.send_ai_stream_abort(
                        generation_id, client_id, history_id
                    )
                    logger.warning(f"[chat_with_llm] this generation has been aborted, generation_id = {generation_id}")
                    return

                await self.ws_list.send_ai_stream_token(
                    generation_id, client_id, history_id, achunk
                )
                await asyncio.sleep(0.06)

            await self.ws_list.send_ai_stream_end(generation_id, client_id, history_id)

        except Exception as e:
            logger.error(f"[chat_with_llm error] {client_id}: {traceback.format_exc()}")

            self.ws_list.abort_generation(client_id, generation_id)
            await self.ws_list.send_ai_stream_abort(
                generation_id,
                client_id,
                history_id,
                reason="error_occurred",
                content=f"{e.__class__.__name__}: {str(e)}"
            )


websocket_list = WebsocketList()
ws_msg_handler = WebsocketMessageHandler(websocket_list)