"""Versioned registry for event handlers and resolved handler chains."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from fnmatch import fnmatchcase

from apix.common.utils.logger import logger
from apix.core.event.base import ApixEventHandler, EventHandlerFunc
from apix.core.event.event_registry import APIX_EVENT_REGISTRY
from apix.core.utils.exception import (
    EventHandlerAlreadyRegisteredError,
    EventHandlerNotRegisteredError,
)


class ApixHandlerRegistry:
    """Store handlers once and cache event-specific chains by version.

    ``priority_buckets`` is the active ordering structure. Handler entries stay
    in ``registry`` after unregistration so events that captured an older chain
    version can still resolve and execute those handlers.

    ``cached_chain`` uses the exact event name as its key. Each list index is a
    chain version; ``None`` marks the current version as invalidated but not yet
    rebuilt, while an empty list is a valid chain with no matching handlers.
    Chains are built lazily when an exact event is published or queried.
    """

    registry: dict[str, ApixEventHandler]
    priority_buckets: dict[float, list[str]]
    cached_chain: dict[str, list[list[str] | None]]

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.registry = {}
        self.priority_buckets = {}
        self.cached_chain = {}
        self._register_order = 0
        self._initialized = True

    @staticmethod
    def _normalise_patterns(
        patterns: Iterable[str],
        *,
        argument_name: str,
    ) -> list[str]:
        """Validate patterns and remove duplicates without changing order."""
        if isinstance(patterns, str):
            patterns = (patterns,)

        supplied = list(patterns)
        if not supplied:
            raise ValueError(f"{argument_name} cannot be empty.")
        if any(
            not isinstance(pattern, str) or not pattern
            for pattern in supplied
        ):
            raise ValueError(
                f"Every pattern in {argument_name} must be a non-empty string."
            )
        return list(dict.fromkeys(supplied))

    @staticmethod
    def _matches_handler(handler: ApixEventHandler, event_name: str) -> bool:
        """Return whether a handler accepts one exact, case-sensitive event."""
        subscribed = any(
            fnmatchcase(event_name, pattern)
            for pattern in handler.subscribe
        )
        filtered = any(
            fnmatchcase(event_name, pattern)
            for pattern in handler.filter_event
        )
        return subscribed and not filtered

    def _iter_active_handler_names(self) -> Iterator[str]:
        """Yield active handler names in deterministic dispatch order."""
        for priority in sorted(self.priority_buckets, reverse=True):
            yield from self.priority_buckets[priority]

    def _find_handler_position(self, handler_name: str) -> tuple[float, int] | None:
        """Return the active bucket and index for a handler name."""
        for priority, bucket in self.priority_buckets.items():
            try:
                return priority, bucket.index(handler_name)
            except ValueError:
                continue
        return None

    def _resolve_between_insertion(
        self,
        between_handlers: tuple[str | None, str | None],
    ) -> tuple[float, int]:
        """Resolve a boundary-based insertion without mutating registry state."""
        left_name, right_name = between_handlers
        left_position = (
            self._find_handler_position(left_name)
            if left_name is not None
            else None
        )
        right_position = (
            self._find_handler_position(right_name)
            if right_name is not None
            else None
        )

        if left_name is not None and left_position is None:
            raise EventHandlerNotRegisteredError(
                f"Handler `{left_name}` is not actively registered."
            )
        if right_name is not None and right_position is None:
            raise EventHandlerNotRegisteredError(
                f"Handler `{right_name}` is not actively registered."
            )

        if left_position is not None and right_position is not None:
            left_priority, left_index = left_position
            right_priority, right_index = right_position
            if left_priority < right_priority or (
                left_priority == right_priority and left_index >= right_index
            ):
                raise ValueError(
                    f"Handler `{left_name}` must be before handler "
                    f"`{right_name}`."
                )

            # When a right boundary exists, insertion is immediately before it.
            return right_priority, right_index

        if left_position is not None:
            priority, index = left_position
            return priority, index + 1

        assert right_position is not None
        return right_position

    def _invalidate_matching_chains(
        self,
        handler: ApixEventHandler,
        *,
        additional_filters: Iterable[str] = (),
    ) -> None:
        """Append an invalid current version for every affected exact event."""
        filters = tuple(additional_filters)
        for event_name, versions in self.cached_chain.items():
            if not self._matches_handler(handler, event_name):
                continue
            if filters and not any(
                fnmatchcase(event_name, pattern)
                for pattern in filters
            ):
                continue
            versions.append(None)

    def get_handlers_chain_for_event(
        self,
        event_name: str,
        version: int | None = None,
    ) -> list[str]:
        """Return the handler-name chain for an exact event and cache version.

        Omitting ``version`` selects the current version. A missing current
        cache is resolved from the active priority buckets and stored before it
        is returned.
        """
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("event_name must be a non-empty string.")

        versions = self.cached_chain.setdefault(event_name, [None])
        selected_version = len(versions) - 1 if version is None else version
        if (
            isinstance(selected_version, bool)
            or not isinstance(selected_version, int)
            or selected_version < 0
            or selected_version >= len(versions)
        ):
            raise ValueError(
                f"Handler chain version {selected_version!r} does not exist "
                f"for event `{event_name}`."
            )

        chain = versions[selected_version]
        if chain is not None:
            return chain

        chain = []
        for handler_name in self._iter_active_handler_names():
            handler = self.registry.get(handler_name)
            if handler is not None and self._matches_handler(handler, event_name):
                chain.append(handler_name)

        versions[selected_version] = chain
        return chain

    def get_current_version_for_event(self, event_name: str) -> int:
        """Resolve the current chain and return its cache version number."""
        self.get_handlers_chain_for_event(event_name)
        return len(self.cached_chain[event_name]) - 1

    def get_current_version_for_event_without_resolve(self, event_name: str) -> int | None:
        """Return cache version number."""
        cached_chain = self.cached_chain.get(event_name)
        if cached_chain is None:
            return None
        return len(cached_chain) - 1

    def register_handler(self, handler_entry: ApixEventHandler) -> None:
        """Register one handler entry and invalidate every affected cache."""
        if not isinstance(handler_entry, ApixEventHandler):
            raise TypeError("handler_entry must be an ApixEventHandler instance.")
        if not handler_entry.name:
            raise ValueError("Handler name cannot be empty.")
        if handler_entry.name in self.registry:
            raise EventHandlerAlreadyRegisteredError(
                f"Handler `{handler_entry.name}` already registered."
            )
        if not callable(handler_entry.callback):
            raise TypeError("Handler callback must be callable.")

        handler_entry.subscribe = self._normalise_patterns(
            handler_entry.subscribe,
            argument_name="subscribe",
        )
        if handler_entry.filter_event:
            handler_entry.filter_event = self._normalise_patterns(
                handler_entry.filter_event,
                argument_name="filter_event",
            )

        between_handlers = handler_entry.between_handlers
        if between_handlers is not None:
            if (
                not isinstance(between_handlers, tuple)
                or len(between_handlers) != 2
            ):
                raise ValueError(
                    "between_handlers must be a tuple containing exactly two "
                    "handler names."
                )
            left_name, right_name = between_handlers
            if left_name is None and right_name is None:
                raise ValueError("between_handlers cannot be (None, None).")
            if any(
                name is not None and (not isinstance(name, str) or not name)
                for name in between_handlers
            ):
                raise ValueError(
                    "Boundary handler names must be non-empty strings or None."
                )
            if left_name is not None and left_name == right_name:
                raise ValueError(
                    "The left and right handlers in between_handlers cannot "
                    "be the same handler."
                )
            if handler_entry.priority is not None:
                raise ValueError(
                    "between_handlers and priority cannot be set together."
                )
            bucket_priority, insert_index = self._resolve_between_insertion(
                between_handlers
            )
        else:
            priority = handler_entry.priority
            if isinstance(priority, bool) or not isinstance(priority, (int, float)):
                raise TypeError(
                    "Handler priority must be a number when between_handlers "
                    "is not set."
                )
            if not math.isfinite(priority):
                raise ValueError("Handler priority must be finite.")
            bucket_priority = priority
            insert_index = len(self.priority_buckets.get(bucket_priority, ()))

        self.registry[handler_entry.name] = handler_entry
        bucket = self.priority_buckets.setdefault(bucket_priority, [])
        bucket.insert(insert_index, handler_entry.name)
        self._invalidate_matching_chains(handler_entry)

        logger.debug(
            f"Registered handler {handler_entry.name}, "
            f"priority={handler_entry.priority}, "
            f"between_handlers={handler_entry.between_handlers}"
        )

    def unregister_handler(
        self,
        handler_name: str,
        event_names: list[str] | None = None,
    ) -> None:
        """Unregister a handler while retaining its registry entry.

        With no ``event_names``, the handler is removed from active priority
        buckets for every event. When exact names or patterns are supplied,
        they are added to ``filter_event`` so only those events are removed.
        """
        handler = self.registry.get(handler_name)
        if handler is None:
            raise EventHandlerNotRegisteredError(
                f"Handler `{handler_name}` not registered."
            )

        if event_names is not None:
            filters = self._normalise_patterns(
                event_names,
                argument_name="event_names",
            )
            new_filters = [
                pattern
                for pattern in filters
                if pattern not in handler.filter_event
            ]
            if not new_filters or self._find_handler_position(handler_name) is None:
                return
            self._invalidate_matching_chains(
                handler,
                additional_filters=new_filters,
            )
            handler.filter_event.extend(new_filters)
            return

        position = self._find_handler_position(handler_name)
        if position is None:
            return

        self._invalidate_matching_chains(handler)
        priority, index = position
        bucket = self.priority_buckets[priority]
        bucket.pop(index)
        if not bucket:
            del self.priority_buckets[priority]

        logger.debug(f"Unregistered handler {handler_name}.")

    def delete_handler_from_registry(
        self,
        handler_name: str,
        event_names: list[str] | None = None,
    ) -> None:
        """Permanently remove a handler entry and all active bucket references.

        ``event_names`` is accepted for API symmetry, but permanent deletion
        affects all subscriptions so every matching exact-event cache is
        invalidated.
        """
        handler = self.registry.get(handler_name)
        if handler is None:
            raise EventHandlerNotRegisteredError(
                f"Handler `{handler_name}` not registered."
            )

        position = self._find_handler_position(handler_name)
        if position is not None:
            self._invalidate_matching_chains(handler)
            priority, index = position
            bucket = self.priority_buckets[priority]
            bucket.pop(index)
            if not bucket:
                del self.priority_buckets[priority]

        del self.registry[handler_name]
        logger.debug(f"Deleted handler {handler_name} from registry.")

    def get_handler(self, handler_name: str) -> ApixEventHandler | None:
        """Return a handler entry by name, or ``None`` when it is unknown."""
        return self.registry.get(handler_name)

    def get_unmatched_subscriptions(self, handler_name: str) -> list[str]:
        """Return subscription patterns that matched no observed event name."""
        handler = self.registry.get(handler_name)
        if handler is None:
            raise EventHandlerNotRegisteredError(
                f"Handler `{handler_name}` not registered."
            )

        event_names = APIX_EVENT_REGISTRY.get_registered_events()
        return [
            subscription
            for subscription in handler.subscribe
            if not any(
                fnmatchcase(event_name, subscription)
                and not any(
                    fnmatchcase(event_name, pattern)
                    for pattern in handler.filter_event
                )
                for event_name in event_names
            )
        ]


APIX_HANDLER_REGISTRY = ApixHandlerRegistry()


def subscribe(
    *event_names: str,
    exist_ok: bool = True,
    priority: float | None = None,
    between_handlers: tuple[str | None, str | None] | None = None,
    filter_event: list[str] | None = None,
    stop_when_error: bool = True,
    time_out: float | None = None,
    background: bool = False,
):
    """Register an async handler for one or more event-name patterns.

    Handler names are unique across the process-global registry. The decorated
    function itself is returned unchanged.

    Event subscription and filtering use case-sensitive
    :func:`fnmatch.fnmatchcase` semantics. The handler chain is resolved lazily
    from the active priority buckets when an exact event name is first published
    or queried for a cache version.

    Args:
        event_names:
            One or more event-name patterns to subscribe to. Exact names and
            ``fnmatchcase`` wildcards are both supported, including ``*``,
            ``?``, and character classes such as ``[a-z]``.

            Duplicate patterns are removed while preserving their first
            occurrence. At least one non-empty pattern is required.

            Matching is case-sensitive. For example, ``"Graph.*"`` matches
            ``"Graph.Start"`` but does not match ``"graph.start"``.

        exist_ok:
            If ``True``, decorating another function with a name that already
            exists in the registry has no effect, and the new function is
            returned without replacing the original handler entry.

            If ``False``, a duplicate function name raises
            :class:`EventHandlerAlreadyRegisteredError`.

            Deduplication is based only on the function name, not on subscribed
            patterns or callback identity.

        priority:
            Numeric handler priority. Higher values are dispatched first.
            Handlers with the same priority retain registration order.

            Defaults to ``1`` when ``between_handlers`` is not specified.
            ``priority`` and ``between_handlers`` cannot be supplied together.

        between_handlers:
            Insert the handler relative to active handler names already stored
            in ``priority_buckets``. Boundary names refer to handler function
            names and must already be actively registered.

            Supported forms:

            1. ``(left_handler, right_handler)``

               Insert after ``left_handler`` and immediately before
               ``right_handler``. Existing handlers between the boundaries
               remain before the new handler.

               Example::

                   Existing order:
                       left_handler
                       handler_a
                       handler_b
                       right_handler

                   Registration:
                       between_handlers=(
                           "left_handler",
                           "right_handler",
                       )

                   Result:
                       left_handler
                       handler_a
                       handler_b
                       new_handler
                       right_handler

               The left boundary must already dispatch before the right
               boundary. Reversed boundaries raise ``ValueError``.

            2. ``(None, right_handler)``

               Insert immediately before ``right_handler``.

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

               Insert immediately after ``left_handler``.

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

            When a right boundary is present, the new handler is inserted into
            the right boundary's priority bucket. With only a left boundary,
            it is inserted into the left boundary's bucket. The handler's own
            ``priority`` metadata remains ``None``.

            ``(None, None)`` is invalid. The two boundaries cannot name the
            same handler, and every non-``None`` boundary must be a non-empty
            string.

        filter_event:
            Optional case-sensitive event-name patterns to exclude after a
            subscription matches. A handler is selected only when the exact
            event name matches at least one ``event_names`` pattern and does
            not match any ``filter_event`` pattern.

            Example::

                @subscribe(
                    "graph.*",
                    filter_event=["graph.internal.*"],
                )
                async def public_graph_handler(event):
                    ...

            The example receives ``"graph.started"`` but not
            ``"graph.internal.snapshot"``.

        stop_when_error:
            If ``True``, synchronous dispatch of later handlers stops when this
            handler raises an exception. If ``False``, dispatch continues with
            the next handler. Background-handler failures never interrupt the
            foreground handler chain.

        time_out:
            Maximum execution time in seconds. ``None`` waits indefinitely.
            Values less than or equal to zero are normalized to ``None``.

        background:
            If ``True``, schedule the handler as a background task without
            waiting for it before dispatching subsequent handlers.

    Dispatch rules:
        1. Each event instance is dispatched in its own task.
        2. Higher-priority buckets dispatch before lower-priority buckets.
        3. Handlers in one bucket retain their explicit or registration order.
        4. ``between_handlers`` determines placement when supplied and cannot
           be combined with an explicit priority.
        5. The exact handler-name chain version is frozen when the event enters
           the local queue. Later registration or unregistration does not
           change the chain used by an already published event.
        6. Events with different exact names may dispatch concurrently.
        7. Calling :meth:`ApixEvent.accept` skips handlers that have not yet
           been dispatched.

    Examples:
        Register handlers by priority::

            @subscribe("graph.*", priority=10)
            async def validate_graph_event(event):
                ...

            @subscribe("graph.*", priority=1)
            async def persist_graph_event(event):
                ...

        Insert a handler before an existing handler::

            @subscribe(
                "graph.*",
                between_handlers=(None, "persist_graph_event"),
            )
            async def enrich_graph_event(event):
                ...

    Returns:
        A decorator that returns the supplied handler function unchanged after
        successful registration or an ``exist_ok`` duplicate.

    Raises:
        ValueError:
            If no event-name pattern is supplied; a pattern is empty;
            ``between_handlers`` is malformed; both boundaries are ``None``;
            boundary names are empty or equal; explicit priority is combined
            with boundaries; boundaries are reversed; or priority is not
            finite.

        TypeError:
            If a priority is not numeric or the decorated callback is not
            callable.

        EventHandlerNotRegisteredError:
            If a non-``None`` boundary handler is not actively registered.

        EventHandlerAlreadyRegisteredError:
            If ``exist_ok`` is ``False`` and the function name already exists
            in the handler registry.
    """
    normalised_event_names = ApixHandlerRegistry._normalise_patterns(
        event_names,
        argument_name="event_names",
    )
    normalised_filters = (
        ApixHandlerRegistry._normalise_patterns(
            filter_event,
            argument_name="filter_event",
        )
        if filter_event
        else []
    )

    if between_handlers is not None:
        if not isinstance(between_handlers, tuple) or len(between_handlers) != 2:
            raise ValueError(
                "between_handlers must be a tuple containing exactly two "
                "handler names."
            )
        left_name, right_name = between_handlers
        if left_name is None and right_name is None:
            raise ValueError("between_handlers cannot be (None, None).")
        if left_name is not None and left_name == right_name:
            raise ValueError(
                "The left and right handlers in between_handlers cannot be "
                "the same handler."
            )
        if any(
            name is not None and (not isinstance(name, str) or not name)
            for name in between_handlers
        ):
            raise ValueError(
                "Boundary handler names must be non-empty strings or None."
            )
        if priority is not None:
            raise ValueError("between_handlers and priority cannot be set together.")
    elif priority is None:
        priority = 1

    if time_out is not None and time_out <= 0:
        time_out = None

    def decorator(func: EventHandlerFunc) -> EventHandlerFunc:
        handler_name = func.__name__
        if handler_name in APIX_HANDLER_REGISTRY.registry:
            if exist_ok:
                return func
            raise EventHandlerAlreadyRegisteredError(
                f"Handler `{handler_name}` already registered."
            )

        register_order = APIX_HANDLER_REGISTRY._register_order
        entry = ApixEventHandler(
            name=handler_name,
            register_order=register_order,
            callback=func,
            subscribe=normalised_event_names.copy(),
            filter_event=normalised_filters.copy(),
            priority=priority,
            between_handlers=between_handlers,
            stop_when_error=stop_when_error,
            time_out=time_out,
            background=background,
        )
        APIX_HANDLER_REGISTRY.register_handler(entry)
        APIX_HANDLER_REGISTRY._register_order += 1
        return func

    return decorator


def unsubscribe(
    handler_name: str,
    event_names: list[str] | None = None,
    *,
    missing_ok: bool = True,
) -> None:
    """Unregister a global handler while retaining old-version execution data."""
    try:
        APIX_HANDLER_REGISTRY.unregister_handler(handler_name, event_names)
    except EventHandlerNotRegisteredError:
        if not missing_ok:
            raise


def get_handler_meta(
    handler_name: str,
) -> dict | None:
    handler = APIX_HANDLER_REGISTRY.get_handler(handler_name)
    return {
        'id': handler.id,
        'name': handler.name,
        'register_order': handler.register_order,
        'subscribe': handler.subscribe,
        'filter_event': handler.filter_event,
        'priority': handler.priority,
        'between_handlers': handler.between_handlers,
        'stop_when_error': handler.stop_when_error,
        'time_out': handler.time_out,
        'background': handler.background,
    }


def get_unmatched_subscriptions(handler_name: str) -> list[str]:
    """Return global handler patterns that matched no observed event name."""
    return APIX_HANDLER_REGISTRY.get_unmatched_subscriptions(handler_name)


def delete_handler_from_registry(
    handler_name: str,
    event_names: list[str] | None = None,
    *,
    missing_ok: bool = True,
) -> None:
    """Permanently delete a handler from the process-global registry."""
    try:
        APIX_HANDLER_REGISTRY.delete_handler_from_registry(
            handler_name,
            event_names,
        )
    except EventHandlerNotRegisteredError:
        if not missing_ok:
            raise


__all__ = [
    "ApixHandlerRegistry",
    "APIX_HANDLER_REGISTRY",
    "delete_handler_from_registry",
    "get_unmatched_subscriptions",
    "subscribe",
    "unsubscribe",
    "get_handler_meta"
]
