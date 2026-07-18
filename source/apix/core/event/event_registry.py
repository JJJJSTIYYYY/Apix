import copy
import uuid
from typing import Tuple

from apix.core.event.base import (
    EventHandlerFunc,
    HandlerEntry,
    HandlerMeta,
)
from apix.common.type.exception import EventHandlerNotRegistered, EventHandlerAlreadyRegistered
from apix.common.utils.logger import logger


class ApixEventRegistry:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._handlers: dict[str, list[HandlerEntry]] = {}
        self._handlers_meta: dict[str, HandlerMeta] = {}
        self._register_order = 0

    def _find_insert_index(
        self,
        handlers: list[HandlerEntry],
        priority: float,
        between_handlers: Tuple[str, str] | None = None,
    ) -> int:
        """
        Find insertion index without sorting.
        """

        if between_handlers:
            left_name, right_name = between_handlers

            left_index = None
            right_index = None
            event_name = None

            for i, handler in enumerate(handlers):
                event_name = handler.subscribe
                if handler.name == left_name:
                    left_index = i

                if handler.name == right_name:
                    right_index = i
                    break

            if left_index is None:
                raise EventHandlerNotRegistered(
                    f"Handler `{left_name}` not registered" + 
                    ("." if event_name is None else f"for event {event_name}.")
                )

            if right_index is None:
                raise EventHandlerNotRegistered(
                    f"Handler `{right_name}` not registered" + 
                    ("." if event_name is None else f"for event {event_name}.")
                )

            # Insert before right handler.
            # If there are handlers between them,
            # new handler will be appended after them.
            return left_index if left_index >= right_index else right_index


        if priority is None:
            return len(handlers)

        # Normal priority insertion:
        # higher priority first,
        # same priority keeps registration order.
        for i, handler in enumerate(handlers):
            if handler.priority is not None and priority > handler.priority:
                return i

        return len(handlers)

    def get_handlers(
        self,
        event_name: str,
    ) -> list[HandlerEntry]:
        """
        Get handlers list by event name.
        """
        return self._handlers.get(
            event_name,
            [],
        )

    def get_handler_meta(
        self,
        handler_name: str,
    ) -> HandlerMeta:
        handler = self._handlers_meta.get(
            handler_name
        )

        if not handler:
            raise EventHandlerNotRegistered(
                f"Handler `{handler_name}` "
                f"not registered."
            )

        return handler

    def get_all_handlers_meta(
        self,
    ) -> dict[str, HandlerMeta]:
        return copy.deepcopy(
            self._handlers_meta
        )

    def subscribe(
        self,
        *event_names: str,
        priority: float | None = None,
        between_handlers: Tuple[str, str] | None = None,
        stop_when_error: bool = True,
        time_out: float = 30,
        background: bool = False,
    ):
        """
        Register handler for one or more events.

        Args:
            event_names: One or more event to listen.
            priority: Handler priority, default 1 if not between_handlers.
            between_handlers:
                Insert this handler between two existing handlers that registered for the same event.
                When specified, this takes precedence over priority ordering.
                The current handler will be placed after the first handler
                and before the second handler.
                Use handler function names as identifiers.
            stop_when_error:
                If True, dispatching stops when this handler raises an exception.
            time_out:
                Max timeout in seconds.
                Any value <= 0 disables timeout.
            background:
                If True, the handler runs in the background without blocking
                subsequent handlers.

        Rules:
            1. Each event instance is dispatched in its own task.
            2. Handlers are dispatched in priority order.
               Higher priority values are dispatched first.
               Handlers with the same priority are dispatched in registration order.
            3. Handlers for different events may be executed concurrently.
            4. If a handler calls event.accept(),
               remaining non-dispatched handlers are skipped.
        """

        if not event_names:
            raise ValueError(
                "At least one event_name is required."
            )

        if time_out <= 0:
            time_out = -1

        if not between_handlers and priority is None:
            priority = 1
        elif between_handlers and priority is not None:
            priority = None

        def decorator(
            func: EventHandlerFunc,
        ) -> EventHandlerFunc:

            handler_name = func.__name__

            if handler_name in self._handlers_meta:
                raise EventHandlerAlreadyRegistered(
                    f"Handler `{handler_name}` "
                    f"already registered."
                )

            register_order = self._register_order
            self._register_order += 1

            self._handlers_meta[handler_name] = {
                "name": handler_name,
                "subscribe": list(event_names),
                "priority": priority,
                "between": between_handlers,
                "register_order": register_order,
                "time_out": time_out,
                "stop_when_error": stop_when_error,
                "background": background
            }

            for event_name in event_names:

                handlers = self._handlers.setdefault(
                    event_name,
                    [],
                )

                handler_id = uuid.uuid4().hex

                entry = HandlerEntry(
                    id=handler_id,
                    name=handler_name,
                    subscribe=event_name,
                    callback=func,
                    priority=priority,
                    register_order=register_order,
                    stop_when_error=stop_when_error,
                    time_out=time_out,
                    background=background,
                )

                insert_index = self._find_insert_index(
                    handlers=handlers,
                    priority=priority,
                    between_handlers=between_handlers,
                )

                handlers.insert(
                    insert_index,
                    entry,
                )

                logger.debug(
                    f"Registered handler "
                    f"{handler_name} "
                    f"for event `{event_name}`, "
                    f"priority={priority}"
                )

            return func

        return decorator


apix_event_registry = ApixEventRegistry()