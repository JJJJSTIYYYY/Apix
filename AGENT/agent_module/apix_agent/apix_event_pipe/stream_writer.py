from enum import Enum
import time
import uuid
from typing import Any, Optional
from langgraph.config import get_stream_writer

from apix_agent.commons.type_def import ApixEventEnvelope, MinimalEnvelopeData


class StreamEvent(str, Enum):
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


class ApixStreamWriter:
    """
    Event sender for LangGraph streaming.

    - Single public method: send_event
    - Internally wraps LangGraph writer
    - Provides extension hook (no plugin logic yet)
    """

    def __init__(
        self,
        trace_id: Optional[str] = None,
    ):
        self._writer = get_stream_writer()
        self._trace_id = trace_id or str(uuid.uuid4())

    # Public API
    def send_event(
        self,
        *,
        event: StreamEvent,
        target_id: str,
        target_platform: str = None,
        data: MinimalEnvelopeData = None,
        trace_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ):
        """
        Send a structured event.

        :param event: event name
        :param target: event target
        :param data: payload
        :param trace_id: optional override
        :param timestamp: optional override
        """

        envelope: ApixEventEnvelope = {
            "event": event.value,
            "target": {
                "id": target_id,
                "platform": target_platform or 'default'
            },
            "data": data,
            "trace_id": trace_id or self._trace_id,
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