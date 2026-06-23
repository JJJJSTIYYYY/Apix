from dataclasses import dataclass
from datetime import datetime
import time
from typing import Any, Awaitable, Callable

from apix_agent.commons.type_def import ApixEventEnvelope, ApixIdentity
from apix_agent.commons.logger import logger


@dataclass(slots=True)
class ApixEventItem:
    event: str
    target: ApixIdentity | None
    event_name: str
    content: Any
    timestamp: float
    generation_id: str | None
    accepted: bool = False

    @classmethod
    def from_envelope(
        cls,
        envelope: ApixEventEnvelope
    ) -> "ApixEventItem":
        data = envelope.get("data", {}) or {}

        return cls(
            event=envelope.get("event"),
            target=envelope.get("target"),
            event_name=data.get("event_name"),
            content=data.get("content"),
            timestamp=envelope.get("timestamp") or time.time(),
            generation_id=envelope.get("generation_id", "-1"),
        )

    def accept(self) -> None:
        '''
        Mark this event item as accepted.

        Once accepted, the event should not be processed by
        subsequent handlers.
        '''
        self.accepted = True

    @property
    def datetime(self) -> datetime:
        '''
        Convert timestamp to datetime object.
        '''
        return datetime.fromtimestamp(self.timestamp)

    def to_envelope(self) -> ApixEventEnvelope:
        return {
            "event": self.event,
            "target": self.target,
            "data": {
                "event_name": self.event_name,
                "content": self.content,
            },
            "timestamp": self.timestamp,
            "generation_id": self.generation_id,
            "blocking": False,
            "block_id": "",
        }


EventHandlerFunc = Callable[
    [ApixEventItem],
    Awaitable[None]
]


@dataclass(slots=True)
class HandlerEntry:
    time_out: int
    stop_when_error: bool
    push_to_user: bool
    priority: int
    register_order: int
    callback: EventHandlerFunc


class EventRegistry:

    _instance = None

    def __new__(cls):
        # Ensure singleton instance
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._handlers: dict[str, list[HandlerEntry]] = {}
        self._register_order = 0

    def on_event(
        self,
        *event_names: str,
        priority: int = 1,
        push_to_user: bool = False,
        stop_when_error: bool = False,
        time_out: int = 30,
    ):
        """
        Register handler for one or more events.

        Example:

        @event_registry.on_event(
            "tool_exec_start",
            "tool_exec_end",
            priority=10,
        )
        async def handler(event):
            ...
        """

        if not event_names:
            raise ValueError(
                "At least one event_name is required."
            )

        def decorator(
            func: EventHandlerFunc,
        ) -> EventHandlerFunc:

            for event_name in event_names:

                handlers = self._handlers.setdefault(
                    event_name,
                    []
                )

                handlers.append(
                    HandlerEntry(
                        time_out=time_out,
                        stop_when_error=stop_when_error,
                        push_to_user=push_to_user,
                        priority=priority,
                        register_order=self._register_order,
                        callback=func,
                    )
                )

                handlers.sort(
                    key=lambda x: (
                        -x.priority,
                        x.register_order,
                    )
                )

                self._register_order += 1

                logger.debug(
                    f"Registered handler "
                    f"{func.__name__} "
                    f"for event `{event_name}`, "
                    f"priority={priority}"
                )

            return func

        return decorator

    def get_handlers(
        self,
        event_name: str,
    ) -> list[HandlerEntry]:
        return self._handlers.get(event_name, [])
    


event_registry = EventRegistry()