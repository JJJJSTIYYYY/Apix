import copy
from uuid import uuid4

from apix.core.event.base import (
    EventHandlerFunc,
    ApixEventHandler,
    HandlerMeta,
)
from apix.core.utils.exception import EventHandlerNotRegisteredError, EventHandlerAlreadyRegisteredError
from apix.common.utils.logger import logger


class ApixEventRegistry:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._handlers: dict[str, list[ApixEventHandler]] = {}
        self._handlers_meta: dict[str, HandlerMeta] = {}
        self._register_order = 0
        self._initialized = True

    def get_handlers(
        self,
        event_name: str,
    ) -> list[ApixEventHandler]:
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
            raise EventHandlerNotRegisteredError(
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

    def unsubscribe(
        self,
        handler_name: str,
        *,
        missing_ok: bool = True,
    ) -> None:
        """Remove one handler from every event to which it is subscribed.

        Args:
            handler_name: Function name used when the handler was registered.
            missing_ok: If ``True``, an unknown handler has no effect. If
                ``False``, it raises :class:`EventHandlerNotRegisteredError`.
        """
        handler_meta = self._handlers_meta.pop(handler_name, None)
        if handler_meta is None:
            if missing_ok:
                return
            raise EventHandlerNotRegisteredError(
                f"Handler `{handler_name}` not registered."
            )

        for event_name in handler_meta["subscribe"]:
            handlers = self._handlers.get(event_name)
            if handlers is None:
                continue

            retained_handlers = [
                handler
                for handler in handlers
                if handler.name != handler_name
            ]
            if retained_handlers:
                self._handlers[event_name] = retained_handlers
            else:
                self._handlers.pop(event_name, None)

        logger.debug(
            f"Unregistered handler {handler_name} from events "
            f"{handler_meta['subscribe']}"
        )

    def _find_insert_index(
        self,
        event_name: str,
        handlers: list[ApixEventHandler],
        priority: float | None,
        between_handlers: tuple[str | None, str | None] | None = None,
    ) -> int:
        """
        Find the insertion index without sorting.

        between_handlers:
            (left_handler, right_handler):
                Insert after left_handler and before right_handler.

            (None, right_handler):
                Insert immediately before right_handler.

            (left_handler, None):
                Insert immediately after left_handler.
        """

        if between_handlers is not None:
            left_name, right_name = between_handlers

            if left_name is None and right_name is None:
                raise ValueError(
                    "between_handlers cannot be (None, None)."
                )

            if (
                left_name is not None
                and right_name is not None
                and left_name == right_name
            ):
                raise ValueError(
                    "The left and right handlers in between_handlers "
                    "cannot be the same handler."
                )

            left_index: int | None = None
            right_index: int | None = None

            for index, handler in enumerate(handlers):
                if left_name is not None and handler.name == left_name:
                    left_index = index

                if right_name is not None and handler.name == right_name:
                    right_index = index

            if left_name is not None and left_index is None:
                raise EventHandlerNotRegisteredError(
                    f"Handler `{left_name}` not registered "
                    f"for event `{event_name}`."
                )

            if right_name is not None and right_index is None:
                raise EventHandlerNotRegisteredError(
                    f"Handler `{right_name}` not registered "
                    f"for event `{event_name}`."
                )

            # Insert between two handlers.
            if left_index is not None and right_index is not None:
                if left_index >= right_index:
                    raise ValueError(
                        f"Handler `{left_name}` must be before "
                        f"handler `{right_name}` for event `{event_name}`."
                    )

                # Insert immediately before the right handler.
                # Existing handlers between left and right remain before
                # the newly registered handler.
                return right_index

            # Insert immediately after the left handler.
            if left_index is not None:
                return left_index + 1

            # Insert immediately before the right handler.
            assert right_index is not None
            return right_index

        if priority is None:
            return len(handlers)

        # Higher priority first.
        # Handlers with the same priority keep registration order.
        for index, handler in enumerate(handlers):
            if (
                handler.priority is not None
                and priority > handler.priority
            ):
                return index

        return len(handlers)


    def subscribe(
        self,
        *event_names: str,
        exist_ok: bool = True,
        priority: float | None = None,
        between_handlers: tuple[str | None, str | None] | None = None,
        stop_when_error: bool = True,
        time_out: float = None,
        background: bool = False,
    ):
        """
        Register a handler for one or more events.

        Args:
            event_names:
                One or more event names to subscribe to.

            exist_ok:
                If ``True``, registering a handler with the same function name
                for the same event(s) has no effect and the existing handler
                is kept. If ``False``, attempting to register a handler with
                the same function name for the same event(s) raises
                ``EventHandlerAlreadyRegisteredError``.

            priority:
                Handler priority. Handlers with higher priority values are
                dispatched first. Handlers with the same priority retain
                their registration order.

                Defaults to ``1`` when ``between_handlers`` is not specified.

                When ``between_handlers`` is specified, it takes precedence
                over this argument, and the registered handler's priority is
                set to ``None``.

            between_handlers:
                Controls the handler's insertion position relative to existing
                handlers registered for the same event.

                Supported forms:

                1. ``(left_handler, right_handler)``

                Insert the new handler after ``left_handler`` and before
                ``right_handler``.

                ``left_handler`` must already appear before
                ``right_handler`` in the current handler list. These two
                arguments represent ordered left and right boundaries;
                they are not interchangeable.

                If other handlers already exist between the two boundary
                handlers, the new handler is inserted immediately before
                ``right_handler``. Existing handlers within the range
                therefore remain before the new handler.

                Example::

                    Existing:
                        left_handler
                        handler_a
                        handler_b
                        right_handler

                    Result:
                        left_handler
                        handler_a
                        handler_b
                        new_handler
                        right_handler

                Passing the boundaries in reverse order raises
                ``ValueError``.

                Example::

                    Existing:
                        handler_a
                        handler_b

                    Invalid:
                        between_handlers=(
                            "handler_b",
                            "handler_a",
                        )

                2. ``(None, right_handler)``

                Insert the new handler immediately before
                ``right_handler``.

                Example::

                    Existing:
                        handler_a
                        right_handler
                        handler_b

                    Result:
                        handler_a
                        new_handler
                        right_handler
                        handler_b

                3. ``(left_handler, None)``

                Insert the new handler immediately after
                ``left_handler``.

                Example::

                    Existing:
                        handler_a
                        left_handler
                        handler_b

                    Result:
                        handler_a
                        left_handler
                        new_handler
                        handler_b

                Invalid forms and constraints:

                - ``(None, None)`` is invalid.
                - Both boundary names cannot refer to the same handler.
                - Every non-``None`` boundary handler must already be
                registered for each subscribed event.
                - When both boundaries are specified, the left boundary
                must appear before the right boundary in the current
                handler list.

                Handler function names are used as boundary identifiers.

            stop_when_error:
                If ``True``, event dispatch stops when this handler raises
                an exception.

            time_out:
                Maximum handler execution time in seconds. The default ``None``
                waits indefinitely. Any value less than or equal to zero
                disables the timeout.

            background:
                If ``True``, the handler runs in the background without
                blocking the dispatch of subsequent handlers.

        Dispatch rules:
            1. Each event instance is dispatched in its own task.
            2. Handlers using priority ordering are dispatched from higher
            priority to lower priority.
            3. Handlers with the same priority retain registration order.
            4. ``between_handlers`` positioning takes precedence over
            priority ordering.
            5. Handlers subscribed to different events may run concurrently.
            6. If a handler calls ``event.accept()``, handlers that have not
            yet been dispatched are skipped.

        Raises:
            ValueError:
                If no event name is supplied, ``between_handlers`` is
                malformed, both boundaries are ``None``, both boundaries
                have the same name, or the supplied left and right
                boundaries are reversed.

            EventHandlerNotRegisteredError:
                If a non-``None`` boundary handler is not registered for one
                of the subscribed events.

            EventHandlerAlreadyRegisteredError:
                If ``exist_ok`` is ``False`` and another handler with the same
                function name has already been registered.
        """

        if not event_names:
            raise ValueError(
                "At least one event_name is required."
            )

        # Prevent duplicate registration when the same event name
        # is passed more than once.
        normalized_event_names = tuple(
            dict.fromkeys(event_names)
        )

        if any(not event_name for event_name in normalized_event_names):
            raise ValueError(
                "event_name cannot be empty."
            )

        if time_out is not None and time_out <= 0:
            time_out = None

        if between_handlers is not None:
            if (
                not isinstance(between_handlers, tuple)
                or len(between_handlers) != 2
            ):
                raise ValueError(
                    "between_handlers must be a tuple containing "
                    "exactly two handler names."
                )

            left_name, right_name = between_handlers

            if left_name is None and right_name is None:
                raise ValueError(
                    "between_handlers cannot be (None, None)."
                )

            if (
                left_name is not None
                and right_name is not None
                and left_name == right_name
            ):
                raise ValueError(
                    "The left and right handlers in between_handlers "
                    "cannot be the same handler."
                )

            # between_handlers takes precedence over priority.
            priority = None

        elif priority is None:
            priority = 1

        def decorator(
            func: EventHandlerFunc,
        ) -> EventHandlerFunc:
            handler_name = func.__name__

            if handler_name in self._handlers_meta:
                if exist_ok:
                    return func
                raise EventHandlerAlreadyRegisteredError(
                    f"Handler `{handler_name}` already registered."
                )

            register_order = self._register_order

            # Validate all subscribed events and calculate their insertion
            # indexes before changing registry state. This prevents partial
            # registration when one event fails validation.
            registration_plan: list[
                tuple[str, int, ApixEventHandler]
            ] = []

            for event_name in normalized_event_names:
                handlers = self._handlers.get(
                    event_name,
                    [],
                )

                insert_index = self._find_insert_index(
                    event_name=event_name,
                    handlers=handlers,
                    priority=priority,
                    between_handlers=between_handlers,
                )

                entry = ApixEventHandler(
                    id=uuid4().hex,
                    name=handler_name,
                    subscribe=event_name,
                    callback=func,
                    priority=priority,
                    register_order=register_order,
                    stop_when_error=stop_when_error,
                    time_out=time_out,
                    background=background,
                )

                registration_plan.append(
                    (
                        event_name,
                        insert_index,
                        entry,
                    )
                )

            # All events have passed validation.
            self._register_order += 1

            self._handlers_meta[handler_name] = {
                "name": handler_name,
                "subscribe": list(normalized_event_names),
                "priority": priority,
                "between": between_handlers,
                "register_order": register_order,
                "time_out": time_out,
                "stop_when_error": stop_when_error,
                "background": background,
            }

            for event_name, insert_index, entry in registration_plan:
                handlers = self._handlers.setdefault(
                    event_name,
                    [],
                )

                handlers.insert(
                    insert_index,
                    entry,
                )

                logger.debug(
                    f"Registered handler {handler_name} "
                    f"for event `{event_name}`, "
                    f"priority={priority}, "
                    f"between_handlers={between_handlers}, "
                    f"insert_index={insert_index}"
                )

            return func

        return decorator


apix_event_registry = ApixEventRegistry()
