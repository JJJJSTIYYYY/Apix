import asyncio
import copy
import time
from typing import Dict, Literal, Optional
from uuid import uuid4

from apix.agent.prebuilt.runtime.stream.agent_stream_writer import AgentStreamWriter
from apix.agent.prebuilt.runtime.generation.base import Generation
from apix.common.lifespan.resource_cleaner import resource_cleaner
from apix.common.utils.logger import logger
from apix.agent.prebuilt.adapter.store.store_adapter import ai_store_adapter
from apix.common.type import ApixIdentity
from apix.config.base_config import GENERATION_TTL


class GenerationManager:
    """Generation state magener.

    This class is used for managing:
    - Context: context for multi-agent invocation per user.
    - Block: 
    """

    def __init__(self):
        self._connections: Dict[str, Dict[str, Generation]] = {} # {user_uid. {generation_id, generation_state}}
        self._active_generation_ids: Dict[str, list[str]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}


    def _get_lock(self, user_uid: str) -> asyncio.Lock:
        lock = self._locks.get(user_uid)
        if not lock:
            lock = asyncio.Lock()
            self._locks[user_uid] = lock
        return lock
    

    def _get_client_generations(self, user_uid: str) -> Dict[str, Generation]:
        gens = self._connections.get(user_uid)
        if gens is None:
            gens = {}
            self._connections[user_uid] = gens
        return gens
    

    def _get_active_list(self, user_uid: str) -> list[str]:
        active_list = self._active_generation_ids.get(user_uid)
        if active_list is None:
            active_list = []
            self._active_generation_ids[user_uid] = active_list
        return active_list
    
    
    async def _set_generation_status(
        self,
        gen: Generation,
        status: Literal["running", "finished", "aborted"]
    ):
        async with gen.status_condition:
            gen.status = status
            gen.status_condition.notify_all()


    def list_running_generations(self, user_uid: str) -> list[str]:
        gens = self._connections.get(user_uid, {})
        return [gid for gid, gen in gens.items() if gen.status == "running"]
    

    async def create_generation(
        self,
        target: ApixIdentity,
    ) -> str:

        new_gen_id = str(uuid4())

        await self.abort_generation(target)

        async with self._get_lock(target["id"]):
            gens = self._get_client_generations(target["id"])
            active_generation_ids = self._get_active_list(target["id"])

            gens[new_gen_id] = Generation(
                generation_id=new_gen_id,
                target=target
            )

            if new_gen_id not in active_generation_ids:
                active_generation_ids.append(new_gen_id)

        return new_gen_id
    
    
    def _ensure_code_block(self, content: str) -> str:
        """
        Ensure markdown code blocks in cache are properly closed. 

        If the number of ``` is odd, append a closing ``` at the end.

        Args:
            content (str): streamed markdown content

        Returns:
            str: content with properly closed code block
        """

        if not content:
            return content

        in_code_block = False

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block

        if in_code_block:
            if not content.endswith("\n"):
                content += "\n"
            content += "```\n"

        return content
    
    
    async def update_cached_tokens(
        self,
        user_uid: str,
        generation_id: str,
        envelope: ApixEventEnvelope,
    ):
        """
        Update cached_tokens based on streaming event.

        This function is extracted from legacy websocket logic and is now
        platform-independent.

        Behavior:
            - Maintains incremental content / think buffers
            - Resets buffers on specific lifecycle events
            - Thread-safe via gen_lock
        """

        gen = self.get_generation(user_uid, generation_id)
        if not gen or gen.status != "running":
            return

        data = envelope.get("data") or {}
        action = data.get("event_name")
        content = data.get("content")

        async with gen.gen_lock:

            # Stream lifecycle start
            if action == "node_stream_start":
                gen.cached_tokens = {
                    "role": "ai",
                    "content": "",
                    "think": "",
                    "extra": {},
                    "info": {},
                    "generation_id": gen.generation_id,
                    "timestamp": time.time()
                }

            # Persist finished: reset buffer
            elif action == "messages_persist_end":
                gen.cached_tokens["content"] = ""
                gen.cached_tokens["think"] = ""

            # Content streaming
            elif action == "content_chunk_rtn":
                if content:
                    gen.cached_tokens["content"] += content

            # Think streaming
            elif action == "think_chunk_rtn":
                if content:
                    gen.cached_tokens["think"] += content

            # Tool execution: clear buffers
            elif action == "tool_exec_chunk_rtn":
                gen.cached_tokens["content"] = ""
                gen.cached_tokens["think"] = ""


    async def persist_cached_tokens(self, gen: Generation):
        async with gen.gen_lock:
            interrupted_msg = copy.deepcopy(gen.cached_tokens)

        if interrupted_msg:
            ts = int(time.time() * 1000)

            content = self._ensure_code_block(interrupted_msg.get("content", ""))
            think = self._ensure_code_block(interrupted_msg.get("think", ""))

            think_endswith = "[Conversation Abort]" if think and not content else ""
            content_endswith = "[Conversation Abort]" if content or not think_endswith else ""

            interrupted_msg.update({
                "content": content + content_endswith,
                "think": think + think_endswith,
                "generation_id": gen.generation_id,
                "timestamp": ts,
            })

            parent_node_id = gen.parent_node_id
            if parent_node_id and parent_node_id != '-':
                await ai_store_adapter.append_message_to_store(
                    gen.user_uid,
                    gen.conversation_uid,
                    interrupted_msg,
                    parent_node_id
                )


    async def abort_generation(self, target: ApixIdentity):
        AgentStreamWriter.clear_all_block(target)
        
        async with self._get_lock(target["id"]):
            gens = self._connections.get(target["id"], {})
            active_generation_ids = self._active_generation_ids.get(target["id"], [])

            for gid in list(active_generation_ids):
                gen = gens.get(gid)
                if gen and gen.conversation_uid == target["conversation_uid"] and gen.status == "running":
                    await self.persist_cached_tokens(gen)
                    await self._set_generation_status(gen, 'aborted')

                    try:
                        active_generation_ids.remove(gid)
                    except ValueError:
                        pass


    async def is_generation_aborted(self, user_uid: str, generation_id: str) -> bool:
        async with self._get_lock(user_uid):
            gens = self._connections.get(user_uid)
            if not gens:
                return True

            gen = gens.get(generation_id)
            return (not gen) or gen.status == "aborted"
        

    async def is_generation_finished(self, user_uid: str, generation_id: str) -> bool:
        async with self._get_lock(user_uid):
            gens = self._connections.get(user_uid)
            if not gens:
                return True

            gen = gens.get(generation_id)
            return (not gen) or gen.status == "finished"
        
        
    async def await_by_conversation_uid(self, user_uid: str, conversation_uid: str):
        async with self._get_lock(user_uid):
            gens = self._connections.get(user_uid, {})

            # Only one running generation in a conversation
            gen = next(
                (
                    g for g in gens.values()
                    if g.conversation_uid == conversation_uid
                    and g.status == "running"
                ),
                None
            )

        if not gen:
            return
        
        logger.trace()

        async with gen.status_condition:
            await gen.status_condition.wait_for(
                lambda: gen.status in ("finished", "aborted")
            )

        logger.trace()


    def get_generation(self, user_uid: str, generation_id: str) -> Optional[Generation]:
        gens = self._connections.get(user_uid)
        if not gens:
            logger.exception(f"Client {user_uid} not register a generation state set")
            return None
        return gens.get(generation_id)
    

    async def clean_expired(self) -> int:
        """
        Clean expired generations across all clients.

        Returns:
            Total number of removed generations

        Behavior:
            - Removes finished/aborted generations older than TTL
            - Safe to call periodically by external scheduler
        """
        if not self._connections:
            return 0

        now = time.time()
        total_removed = 0

        for user_uid, gens in list(self._connections.items()):
            if not gens:
                continue

            async with self._get_lock(user_uid):
                to_delete = []

                for gen_id, gen in gens.items():
                    if gen.status == "running":
                        continue

                    age = now - gen.created_at
                    if age > GENERATION_TTL:
                        to_delete.append(gen_id)

                for gen_id in to_delete:
                    gens.pop(gen_id, None)

                    active_generation_ids = self._active_generation_ids.get(user_uid, [])
                    try:
                        active_generation_ids.remove(gen_id)
                    except ValueError:
                        pass

                if to_delete:
                    removed = len(to_delete)
                    total_removed += removed
                    logger.info(f"Client {user_uid}: removed {removed} generation(s)")

        return total_removed


generation_manager = GenerationManager()


@resource_cleaner.auto_clear
async def clean_ws():
    return await generation_manager.clean_expired()