from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Tuple, TypedDict
from datetime import datetime

from apix.config.base_config import EVENT_HANDLER_DEFAULT_TIME_OUT


class EventType(str, Enum):
    WORKFLOW = 'workflow'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'


@dataclass(slots=True)
class ApixEvent:
    event_id: str
    event_type: EventType
    event_name: str
    context: Any
    timestamp: float
    accepted: bool = False

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

EventHandlerFunc = Callable[
    [ApixEvent],
    Awaitable[None]
]

class HandlerMeta(TypedDict):
    name: str
    subscribe: list[str]
    priority: float | None
    between: Tuple[str, str] | None
    register_order: int
    stop_when_error: bool
    time_out: float
    background: bool

@dataclass(slots=True)
class HandlerEntry:
    id: str
    name: str
    subscribe: str
    callback: EventHandlerFunc
    priority: float | None
    register_order: int
    stop_when_error: bool = field(default=True)
    time_out: float = field(default=EVENT_HANDLER_DEFAULT_TIME_OUT)
    background: bool = field(default=False)