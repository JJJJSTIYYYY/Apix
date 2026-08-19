from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, TypedDict
from datetime import datetime
from uuid import uuid4


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
    _handler_chain_version: int | None = None

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


# # Deprecated ApixEventHandler schema.
# @dataclass(slots=True)
# class ApixEventHandler:
#     id: str
#     name: str
#     subscribe: list[str]
#     callback: EventHandlerFunc | None
#     priority: float | None
#     register_order: int
#     stop_when_error: bool = field(default=True)
#     time_out: float = field(default=-1)
#     background: bool = field(default=False)


@dataclass(slots=True)
class ApixEventHandler:
    name: str
    register_order: int
    callback: EventHandlerFunc | None
    id: str = field(default_factory=lambda: "handler-"+uuid4().hex)
    subscribe: list[str] = field(default_factory=list)
    filter_event: list[str] = field(default_factory=list)
    priority: int | None = field(default=None)
    between_handlers: tuple[str | None, str | None] | None = field(
        default=None
    )
    stop_when_error: bool = field(default=True)
    time_out: float | None = field(default=None)
    background: bool = field(default=False)


ChannelName = Literal["builtin", "mailbox", "mailtruck"]
