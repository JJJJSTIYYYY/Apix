import asyncio
import hashlib
import json
import time
import uuid

from enum import Enum
from typing import Any, Optional

from langgraph.config import get_stream_writer

from apix_agent.commons.type_def import (
    ApixEventEnvelope,
    MinimalEnvelopeData,
    ApixIdentity,
)

from apix_agent.commons.logger import logger


class AgentStreamEvent(str, Enum):
    ESSENTIAL_INFO_RETURN = 'essential_info_return'
    LLM_STREAM_START = "llm_stream_start"
    LLM_CHUNK_RETURN = "llm_chunk_return"
    LLM_STREAM_END = "llm_stream_end"
    LLM_STREAM_ERROR = "llm_stream_error"
    AI_MESSAGE_RETURN = "ai_message_return"
    TOOL_MESSAGE_RETURN = "tool_message_return"
    TOOL_EXEC_START = "tool_exec_start"
    TOOL_EXEC_MIDDLE = "tool_exec_middle"
    TOOL_EXEC_END = "tool_exec_end"
    RUNTIME_WARNING = "runtime_warning"
    ERROR_OCCURRED = "error_occurred"


class AgentStreamWriter:

    # target_hash -> block_id -> future
    _blocking_futures: dict[str, dict[str, asyncio.Future]] = {}

    def __init__(
        self,
        generation_id: Optional[str] = None,
    ):
        self._writer = get_stream_writer()
        self._generation_id = generation_id or str(uuid.uuid4())

    @staticmethod
    def _target_hash(
        target: ApixIdentity,
    ) -> str:
        """
        Build stable hash key for target.

        Notes:
        - Use sorted json serialization to ensure stable order
        - Avoid Python built-in hash(), because it is process-randomized
        """

        target_json = target.get("id") + ':' + target.get("conversation_id")

        return hashlib.sha256(
            target_json.encode("utf-8")
        ).hexdigest()

    # Public API
    def send_event(
        self,
        *,
        event: AgentStreamEvent,
        target: ApixIdentity,
        data: MinimalEnvelopeData = None,
        generation_id: Optional[str] = None,
        timestamp: Optional[float] = None,
        block_id: Optional[str] = None,
        blocking: bool = False,
    ):
        """
        Send structured event while in agent loop.
        Can be called from inside any [`StateGraph`][langgraph.graph.StateGraph] node or
        functional API [`task`][langgraph.func.task].

        Args:
            event: Event enum.
            target: Event receiver. 
                !!! This receiver serves only as a placeholder; it is not the real receiver. 
                !!! For APIX streams, the target is restricted to the event originator, as this rule avoids accidental cross‑streaming.
            data: Event data, should contains event_name and content.
        """

        envelope: ApixEventEnvelope = {
            "event": event.value,
            "target": target,
            "data": data,
            "generation_id": generation_id or self._generation_id,
            "timestamp": timestamp or time.time(),
            "blocking": blocking,
            "block_id": block_id,
        }

        self._writer(envelope)

    # Public API
    async def send_blocking_event(
        self,
        *,
        event: AgentStreamEvent,
        target: ApixIdentity,
        data: MinimalEnvelopeData = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Send blocking event and wait for acknowledgment result while in agent loop.
        Can be called from inside any [`StateGraph`][langgraph.graph.StateGraph] node or
        functional API [`task`][langgraph.func.task].
        """

        block_id = uuid.uuid4().hex

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        target_hash = self._target_hash(target)

        if target_hash not in self._blocking_futures:
            self._blocking_futures[target_hash] = {}

        self._blocking_futures[target_hash][block_id] = future

        data = data or {}
        data["block_id"] = block_id

        self.send_event(
            event=event,
            target=target,
            data=data,
            block_id=block_id,
            blocking=True,
        )

        logger.warning(
            f"Block and wait... "
            f"target={target_hash} "
            f"block_id={block_id}"
        )

        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout)
            else:
                result = await future

            logger.success(
                f"Get result. "
                f"target={target_hash} "
                f"block_id={block_id}"
            )

            return result

        finally:

            target_futures = self._blocking_futures.get(target_hash)

            if target_futures:
                target_futures.pop(block_id, None)

                # Auto cleanup empty target bucket
                if not target_futures:
                    self._blocking_futures.pop(target_hash, None)

    async def block_for_permission(
        self,
        *,
        event: AgentStreamEvent,
        target: ApixIdentity,
        data: MinimalEnvelopeData = None,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Send blocking event and wait for user's agreement.
        """

        pass

    @classmethod
    def resolve_block(
        cls,
        *,
        target: ApixIdentity,
        block_id: str,
        result: Any = None,
    ) -> bool:
        """
        Resolve blocking event by target + block_id.
        """

        target_hash = cls._target_hash(target)

        future = (
            cls._blocking_futures
            .get(target_hash, {})
            .get(block_id)
        )

        if not future:
            return False

        if future.done():
            return False

        future.set_result(result)

        return True

    @classmethod
    def cancel_block(
        cls,
        *,
        target: ApixIdentity,
        block_id: str,
    ) -> bool:
        """
        Release blocking future with None result.

        Semantic:
        - blocking wait ends
        - no result received
        - coroutine continues execution
        """

        target_hash = cls._target_hash(target)

        future = (
            cls._blocking_futures
            .get(target_hash, {})
            .get(block_id)
        )

        if not future:
            return False

        if future.done():
            return False

        # Continue execution with empty result
        future.set_result(None)

        return True

    @classmethod
    def clear_all_block(
        cls,
        target: ApixIdentity,
    ) -> int:
        """
        Release all blocking futures with None result.

        Returns:
            int: released future count
        """

        target_hash = cls._target_hash(target)

        logger.warning(
            f"Clear block... "
            f"target={target_hash} "
        )

        target_futures = cls._blocking_futures.get(target_hash)

        if not target_futures:
            return 0

        cleared_count = 0

        for future in target_futures.values():

            if future.done():
                continue

            # Continue execution with empty result
            future.set_result(None)

            cleared_count += 1

        cls._blocking_futures.pop(target_hash, None)

        logger.warning(
            f"Released {cleared_count} blocking futures "
            f"for target={target_hash}"
        )

        return cleared_count