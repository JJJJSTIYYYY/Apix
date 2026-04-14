import asyncio
import copy
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from uuid import uuid4
from fastapi import WebSocket
import traceback

from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.agent import ai_agent
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.commons.type_def import MessagesState
from apix_agent.global_config import AGENT_SERVICE_ID


@dataclass
class GenerationState:
    """
    State for a single AI generation.
    One generation == one AI invoke lifecycle.
    """
    generation_id: str
    client_id: str
    history_id: str
    # {"role": "ai", "content": "", "think": "", "extra": {}, "info": {}, "generation_id": "", "timestamp": int}
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
    is_aborted: bool = False

    # Protect cache_tokens concurrent access
    gen_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class UserSocketContext:
    """
    WebSocket context for one client.
    """
    websocket: WebSocket
    client_id: str

    # Currently active generation (front-stage)
    active_generation_id: Optional[str] = None

    # All generations for this client
    generations: Dict[str, GenerationState] = field(default_factory=dict)

    # Ensure websocket.send_json is serialized
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class WebsocketList:
    """
    WebSocket connection and event routing manager.
    """

    def __init__(self):
        # key: client_id
        self._connections: Dict[str, UserSocketContext] = {}

    async def register(
        self,
        websocket: WebSocket,
        client_id: str,
    ):
        """
        Register a websocket connection.
        """
        # Handle duplicate connections (same client_id reconnect)
        old_ctx = self._connections.get(client_id)
        if old_ctx:
            # Abort all existing generations silently
            for gen in old_ctx.generations.values():
                gen.is_aborted = True

            # NOTE:
            # Do NOT close old websocket here.
            # FastAPI / ASGI layer should manage websocket lifecycle.

        # Replace with new context
        self._connections[client_id] = UserSocketContext(
            websocket=websocket,
            client_id=client_id,
        )

    def unregister(self, client_id: str):
        """
        Unregister websocket connection.
        """
        ctx = self._connections.pop(client_id, None)
        if not ctx:
            return

        # Cleanup generations
        for gen in ctx.generations.values():
            gen.is_aborted = True

        ctx.generations.clear()
        ctx.active_generation_id = None

    async def create_generation(self, client_id: str, history_id: str, append_cache_memory: bool = True) -> str:
        """
        Create a new generation and abort previous active one.
        """
        ctx = self._get_ctx(client_id)
        new_gen_id = str(uuid4())

        # Abort previous active generation
        if ctx.active_generation_id:
            old_gen = ctx.generations.get(ctx.active_generation_id)
            if old_gen:
                old_gen.is_aborted = True
                interrupted_msg = None

                if append_cache_memory:
                    async with old_gen.gen_lock:
                        if old_gen.cache_tokens.get("content") or old_gen.cache_tokens.get("think"):
                            interrupted_msg = copy.deepcopy(old_gen.cache_tokens)
                            
                    # TODO: FIX BUG caused by append_to_messages()
                    if interrupted_msg:
                        timestamp = time.time() * 1_000_000
                        content = interrupted_msg.get("content") or ""
                        think = interrupted_msg.get("think") or ""
                        interrupted_msg.update({
                            "content": content + ("[Conversation Abort]" if content else ""),
                            "think": think + ("[Conversation Abort]" if think else ""),
                            "generation_id": old_gen.generation_id,
                            "timestamp": timestamp,
                        })
                        await ai_context_manager.append_to_messages(
                            client_id,
                            history_id,
                            interrupted_msg,
                        )

        # Register new generation
        ctx.generations[new_gen_id] = GenerationState(new_gen_id, client_id, history_id)
        ctx.active_generation_id = new_gen_id

        return new_gen_id

    def abort_generation(
        self,
        client_id: str,
        generation_id: str,
    ):
        """
        Abort a specific generation.
        """
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        if gen:
            gen.is_aborted = True

    def is_generation_aborted(
        self,
        client_id: str,
        generation_id: str,
    ) -> bool:
        """
        Check whether a generation has been aborted.
        """
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        return gen.is_aborted if gen else True

    def _get_ctx(self, client_id: str) -> UserSocketContext:
        ctx = self._connections.get(client_id)
        if not ctx:
            raise RuntimeError(f"WebSocket not registered, client id: {client_id}")
        return ctx

    async def send_ai_stream_token(
        self,
        generation_id: str,
        client_id: str,
        history_id: str,
        delta: dict,
    ):
        """
        Send a single token delta.
        """
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)

        # Stop sending token if generation is aborted
        if not gen or gen.is_aborted:
            await self.send_ai_stream_abort(generation_id, client_id, history_id)
            return

        for action, content in delta.items():
            async with gen.gen_lock:
                if action == "node_stream_end" or action == "node_stream_start":
                    gen.cache_tokens = {
                        "role": "ai",
                        "content": "",
                        "think": "",
                        "extra": {},
                        "info": {},
                        "generation_id": "",
                        "timestamp": 0
                    }

                gen.cache_tokens.update({
                    "content": gen.cache_tokens.get("content") + (content if action == 'content_chunk_rtn' else ""),
                    "think": gen.cache_tokens.get("think") + (content if action == 'think_chunk_rtn' else ""),
                })

            payload = {
                "action": action,
                "ts": int(time.time()),
                "generation_id": generation_id,
                "data": {
                    "client_id": client_id,
                    "history_id": history_id,
                    "messages": {
                        "role": "ai",
                        "content": content if action == 'content_chunk_rtn' else "",
                        "think": content if action == 'think_chunk_rtn' else "",
                        "extra": content if action == 'tool_chunk_rtn' else {},
                        "info": content if action == 'info_chunk_rtn' else {},
                        "todos": content if action == 'todo_chunk_rtn' else [],
                        "msg_cursor": None,
                        "created_at": None,
                    },
                },
            }

            async with ctx.send_lock:
                await ctx.websocket.send_json(payload)

    async def send_ai_stream_start(
        self,
        generation_id: str,
        client_id: str,
        history_id: str,
    ):
        """
        Send final AI message after streaming completes.
        """
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)

        # Do not finalize aborted generations
        if not gen or gen.is_aborted:
            return

        payload = {
            "action": "msg_stream_start",
            "ts": int(time.time()),
            "generation_id": generation_id,
            "data": {
                "client_id": client_id,
                "history_id": history_id,
                "messages": {},
            },
        }

        async with ctx.send_lock:
            await ctx.websocket.send_json(payload)

    async def send_ai_stream_end(
        self,
        generation_id: str,
        client_id: str,
        history_id: str,
        reason: str = "graph_finish"
    ):
        """
        Send final AI message after streaming completes.
        """
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)

        # Do not finalize aborted generations
        if not gen or gen.is_aborted:
            return

        payload = {
            "action": "msg_stream_end",
            "ts": int(time.time()),
            "generation_id": generation_id,
            "data": {
                "client_id": client_id,
                "history_id": history_id,
                "reason": reason,
            },
        }

        async with ctx.send_lock:
            await ctx.websocket.send_json(payload)

        gen.is_aborted = True

    async def send_ai_stream_abort(
        self,
        generation_id: str,
        client_id: str,
        history_id: str,
        reason: str = "user_interrupt",
        content: str = ""
    ):
        """
        Notify client that a generation has been aborted.
        """
        ctx = self._get_ctx(client_id)
        gen = ctx.generations.get(generation_id)
        if not gen:
            return

        payload = {
            "action": "msg_stream_abort",
            "ts": int(time.time()),
            "generation_id": generation_id,
            "data": {
                "client_id": client_id,
                "history_id": history_id,
                "reason": reason,
                "content": content,
            },
        }

        async with ctx.send_lock:
            await ctx.websocket.send_json(payload)

    async def send_tool_event(
        self,
        task_id: str,
        client_id: str,
        history_id: str,
        tool_message: dict,
    ):
        """
        Send tool-related events.

        tool_message:
            Must match your existing tool message structure.
        """
        ctx = self._get_ctx(client_id)

        payload = {
            "action": "tool_return",
            "ts": int(time.time()),
            "generation_id": task_id,
            "data": {
                "task_id": task_id,
                "client_id": client_id,
                "history_id": history_id,
                "messages": tool_message,
            },
        }

        async with ctx.send_lock:
            await ctx.websocket.send_json(payload)

        # NOTE:
        # Tool events are NEVER blocked by generation abort.


class WebsocketMessageHandler:

    def __init__(self, ws_lst: WebsocketList):
        self.ws_list = ws_lst

    async def return_error_msg(self, generation_id: str, client_id: str, history_id: str, error_msg: str):
        """
        Chat with LLM agent and get completions.
        """
        logger.trace('[websocket_manager.py] [WebsocketMessageHandler] [return_error_msg] Enter')
        try:
            await self.ws_list.send_ai_stream_start(
                generation_id=generation_id,
                client_id=client_id,
                history_id=history_id
            )
            raise RuntimeError(error_msg)

        except Exception as e:
            logger.error(f"[chat_with_llm error] {client_id}: {e}")

            await self.ws_list.send_ai_stream_abort(
                generation_id,
                client_id,
                history_id,
                reason="error_occured",
                content=f"Error Occured: {e}"
            )
            return

    async def chat_with_llm(self, generation_id, payload: dict):
        """
        Chat with LLM agent and get completions.
        """
        logger.trace('[websocket_manager.py] [WebsocketMessageHandler] [chat_with_llm] Enter')
        try:
            data = payload.get("data") or {}
            client_id = data.get("client_id")
            session_id = data.get("session_id")
            history_id = data.get("history_id")
            message = data.get("messages", {})
            config = data.get("config", {})
            
            enable_agent_assign = bool(config.get("agent_assign", False))
            enable_agent_swarm = bool(config.get("agent_swarm", False))
            agent_role = "agent"
            if enable_agent_assign:
                agent_role = "main_agent"
            if enable_agent_swarm:
                agent_role = "team_leader"

            if not isinstance(message, dict):
                class_name = type(message).__name__
                raise ValueError(f"[chat_with_llm] Unexpected data type: message is {class_name}, expected dict.")

            timestamp = time.time() * 1_000_000
            initial_state: MessagesState = {
                "agent_name": "APIX",
                "agent_role": agent_role,
                "client_id": client_id,
                "session_id": session_id,
                "history_id": history_id,
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
                "documents": [],
            }

            astream = await ai_agent.submit_agent_task(initial_state, config, "MAIN")

            await self.ws_list.send_ai_stream_start(
                generation_id=generation_id,
                client_id=client_id,
                history_id=history_id
            )

            async for achunk in astream:
                if websocket_list.is_generation_aborted(client_id, generation_id):
                    logger.warning(
                        f"[chat_with_llm] generation aborted: client={client_id}, generation={generation_id}"
                    )
                    await astream.aclose()
                    await self.ws_list.send_ai_stream_abort(
                        generation_id, client_id, history_id
                    )
                    return

                await self.ws_list.send_ai_stream_token(
                    generation_id=generation_id,
                    client_id=client_id,
                    history_id=history_id,
                    delta=achunk,
                )

            await self.ws_list.send_ai_stream_end(
                generation_id=generation_id,
                client_id=client_id,
                history_id=history_id
            )

        except Exception as e:
            logger.error(f"[chat_with_llm error] {client_id}: {traceback.format_exc()}")

            await self.ws_list.send_ai_stream_abort(
                generation_id,
                client_id,
                history_id,
                reason="error_occured",
                content=f"Error Occured: {e.__class__.__name__}: {str(e)}"
            )
            return


websocket_list = WebsocketList()
ws_msg_handler = WebsocketMessageHandler(websocket_list)
