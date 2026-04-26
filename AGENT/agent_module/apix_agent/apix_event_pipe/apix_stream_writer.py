from abc import ABC, abstractmethod

from enum import Enum
import time
import uuid
from typing import Any, Optional
from langgraph.config import get_stream_writer

from apix_agent.commons.type_def import ApixEventEnvelope, MinimalEnvelopeData


class ApixStreamWriter:
    """
    Event sender for Apix streaming.

    - Single public method: send_event
    - Internally wraps LangGraph writer
    - Provides extension hook (no plugin logic yet)
    """

    def __init__(
        self,
        trace_id: Optional[str] = None,
    ):
        self._writer = None
        self._trace_id = trace_id or str(uuid.uuid4())

    # Public API
    def send_event(
        self,
        *,
        event: Any,
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