import asyncio
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Literal
from uuid import uuid4

from apix.common.utils.logger import logger


class EventType(str, Enum):
    WORKFLOW = 'workflow'
    LIFECYCLE = 'lifecycle'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'


@dataclass(frozen=True, slots=True)
class ApixEventError:
    """Serializable failure details without references to live traceback frames."""

    handler_name: str
    phase: Literal["core_func", "on_has_error", "on_accepted", "on_error"]
    exception_type: str
    message: str
    traceback: str


@dataclass(slots=True)
class ApixEvent:
    event_id: str
    event_type: EventType
    event_name: str
    context: Any
    timestamp: float
    accepted: bool = False
    error_stack: list[ApixEventError] = field(default_factory=list)

    def accept(self) -> None:
        '''
        Mark this event item as accepted.

        Once accepted, subsequent handlers skip their core functions but
        still receive applicable error and acceptance notifications.
        '''
        self.accepted = True

    @property
    def has_error(self) -> bool:
        """Return whether a foreground handler has recorded a failure."""
        return bool(self.error_stack)

    @property
    def datetime(self) -> datetime:
        '''
        Convert timestamp to datetime object.
        '''
        return datetime.fromtimestamp(self.timestamp)


EventHandlerFunc = Callable[[ApixEvent], Awaitable[None]]
EventHandlerErrorFunc = Callable[[ApixEvent, Exception], Awaitable[None]]


class ApixEventHandler:
    """Execute a core function with notifications about preceding handlers.

    ``on_has_error`` handles upstream failures only. ``on_error`` receives
    this handler's own uncaught exception after it has been logged and, for
    foreground handlers, recorded. Local try/except/finally blocks may still
    handle recovery and cleanup without reporting an event failure.
    Registration metadata is assigned by :func:`subscribe`.
    """

    id: str
    name: str
    subscribe: list[str]
    filter_event: list[str]
    core_func: EventHandlerFunc
    on_accepted: EventHandlerFunc
    on_has_error: EventHandlerFunc
    on_error: EventHandlerErrorFunc
    stop_when_error: bool
    time_out: float | None
    background: bool
    priority: float | None
    between_handlers: tuple[str | None, str | None] | None
    _register_order: float

    def __init__(
        self,
        core_func: EventHandlerFunc,
        on_accepted: EventHandlerFunc | None = None,
        on_has_error: EventHandlerFunc | None = None,
        on_error: EventHandlerErrorFunc | None = None,
        *,
        stop_when_error: bool = True,
        time_out: float | None = None,
        background: bool = False,
    ) -> None:
        for callback in (core_func, on_accepted, on_has_error, on_error):
            if callback is not None and not callable(callback):
                raise TypeError("Handler functions must be callable.")
        if core_func is None:
            raise TypeError("core_func must be callable.")
        self.core_func: EventHandlerFunc = core_func
        self.on_accepted: EventHandlerFunc | None = on_accepted
        self.on_has_error: EventHandlerFunc | None = on_has_error
        self.on_error: EventHandlerErrorFunc | None = on_error
        self.stop_when_error = stop_when_error
        self.time_out = time_out if time_out is not None and time_out > 0 else None
        self.background = background
        self.name = getattr(core_func, "__name__", type(core_func).__name__)
        self.id = "handler-" + uuid4().hex
        self._register_order = -1
        self.subscribe: list[str] = []
        self.filter_event: list[str] = []
        self.priority: float | None = None
        self.between_handlers: tuple[str | None, str | None] | None = None

    @property
    def __name__(self) -> str:
        """Expose the registered name for decorator and inspection tools."""
        return self.name

    async def __call__(self, event: ApixEvent) -> None:
        """Use the same execution contract when called directly."""
        await self.execute(event)

    async def execute(self, event: ApixEvent) -> None:
        """Notify about upstream state, then conditionally execute the core.

        Error notification precedes acceptance notification when both apply.
        Each upstream notification runs at most once. State is checked again after
        notification, so accepting the event there also suppresses the core.
        A timeout applies separately to each invoked function. Cancellation
        propagates; other failures are logged and foreground failures are
        appended to the event without terminating dispatch.

        Each failed core or upstream notification calls ``on_error(event, exc)``
        once. A failure in ``on_error`` is recorded without recursive handling.
        Successful error handling does not remove the original error or retry
        the failed function. Cancellation propagates without calling on_error.
        Background failures still invoke on_error but never enter error_stack.
        """
        if event.has_error and self.on_has_error is not None:
            await self._execute_func(self.on_has_error, "on_has_error", event)
        if event.accepted:
            if self.on_accepted is not None:
                await self._execute_func(self.on_accepted, "on_accepted", event)
            return
        if event.has_error and self.stop_when_error:
            return
        await self._execute_func(self.core_func, "core_func", event)

    async def _execute_func(
        self,
        func: Callable[..., Awaitable[None]],
        phase: Literal["core_func", "on_has_error", "on_accepted", "on_error"],
        event: ApixEvent,
        *args: Any,
    ) -> None:
        """Run one phase and report its own failure without recursive hooks."""
        try:
            if self.time_out is None:
                await func(event, *args)
            else:
                async with asyncio.timeout(self.time_out):
                    await func(event, *args)
        except Exception as exc:
            error = ApixEventError(
                handler_name=self.name,
                phase=phase,
                exception_type=type(exc).__name__,
                message=str(exc),
                traceback=traceback.format_exc(),
            )
            if not self.background:
                event.error_stack.append(error)
            logger.error(
                f"Handler failed: event={event.event_name}, "
                f"handler={self.name}, phase={phase}, "
                f"error={error.exception_type}: {error.message}\n"
                f"{error.traceback}"
            )
            if phase != "on_error" and self.on_error is not None:
                await self._execute_func(self.on_error, "on_error", event, exc)

    def add_has_error_callback(self, callback: EventHandlerFunc, *, exist_ok: bool = True) -> None:
        """Add a callback to be invoked when an upstream handler has failed.

        The callback is invoked once per event if the event has an error in error_stack, before the core function.
        """
        if not callable(callback):
            raise TypeError("Callback must be callable.")
        if self.on_has_error is not None and not exist_ok:
            raise ValueError("on_has_error already set.")
        self.on_has_error = callback

    def add_on_accepted_callback(self, callback: EventHandlerFunc, *, exist_ok: bool = True) -> None:
        """Add a callback to be invoked when the event has been accepted.

        The callback is invoked once per event if the event has been accepted, before the core function.
        """
        if not callable(callback):
            raise TypeError("Callback must be callable.")
        if self.on_accepted is not None and not exist_ok:
            raise ValueError("on_accepted already set.")
        self.on_accepted = callback

    def add_on_error_callback(self, callback: EventHandlerErrorFunc, *, exist_ok: bool = True) -> None:
        """Add a callback to be invoked when this handler has failed.

        The callback is invoked once per event if the core function fails.
        """
        if not callable(callback):
            raise TypeError("Callback must be callable.")
        if self.on_error is not None and not exist_ok:
            raise ValueError("on_error already set.")
        self.on_error = callback


ChannelType = Literal["builtin", "mailbox", "mailtruck"]
