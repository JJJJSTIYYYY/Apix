from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, TypedDict
from datetime import datetime


class EventType(str, Enum):
    WORKFLOW = 'workflow'
    LIFECYCLE = 'lifecycle'
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
    between: tuple[str, str] | None
    register_order: int
    stop_when_error: bool
    time_out: float
    background: bool


class Subscribe(TypedDict):
    event: str
    type: Literal['include', 'except']


@dataclass(slots=True)
class HandlerEntry:
    id: str
    name: str
    subscribe: list[Subscribe]
    callback: EventHandlerFunc | None
    priority: float | None
    register_order: int
    stop_when_error: bool = field(default=True)
    time_out: float = field(default=-1)
    background: bool = field(default=False)


ChannelName = Literal["builtin", "mailbox", "mailtruck"]
