from enum import Enum
import time
import uuid
from typing import Any, Optional
from langgraph.config import get_stream_writer

from apix_agent.commons.type_def import ApixEventEnvelope, MinimalEnvelopeData, ApixEventEnvelopeTarget
# from apix_agent.apix_event_pipe.apix_stream_writer import ApixStreamWriter


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
    """
    Event sender for LangGraph streaming.

    - Single public method: send_event
    - Internally wraps LangGraph writer
    - Provides extension hook (no plugin logic yet)
    """

    def __init__(
        self,
        generation_id: Optional[str] = None,
    ):
        self._writer = get_stream_writer()
        self._generation_id = generation_id or str(uuid.uuid4())

    # Public API
    def send_event(
        self,
        *,
        event: AgentStreamEvent,
        target: ApixEventEnvelopeTarget,
        data: MinimalEnvelopeData = None,
        generation_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ):
        """
        Send a structured event.

        :param event: event name
        :param target: event target
        :param data: payload
        :param generation_id: optional override
        :param timestamp: optional override
        """

        envelope: ApixEventEnvelope = {
            "event": event.value,
            "target": target,
            "data": data,
            "generation_id": generation_id or self._generation_id,
            "timestamp": timestamp or time.time(),
        }

        # Extension Hook (pre-send)
        envelope = self._before_send(envelope)

        # Core send
        self._writer(envelope)

        # Extension Hook (post-send)
        self._after_send(envelope)


    # Extension hooks
    def _before_send(self, envelope: ApixEventEnvelope) -> ApixEventEnvelope:
        """
        Hook before sending event.

        Can be overridden in subclass for:
        - logging
        - mutation
        - filtering
        """
        return envelope

    def _after_send(self, envelope: ApixEventEnvelope) -> None:
        """
        Hook after sending event.

        Can be overridden in subclass for:
        - metrics
        - side effects
        """
        pass