"""Current handler registry with lazily resolved event-specific chains."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from copy import copy
from fnmatch import fnmatchcase

from apix.common.utils.logger import logger
from apix.core.event.base import ApixEventHandler, EventHandlerFunc
from apix.core.event.event_registry import APIX_EVENT_REGISTRY
from apix.core.utils.exception import (
    EventHandlerAlreadyRegisteredError,
    EventHandlerNotRegisteredError,
)


class ApixHandlerRegistry:
    """Store current handlers and one ordered name chain per exact event.

    ``priority_buckets`` determines dispatch order. Missing cache keys and
    ``None`` require rebuilding; an empty list is a valid cached result.
    Registration changes invalidate affected entries without modifying lists
    already held by dispatch tasks. The consumer resolves chains at dequeue.
    """

    registry: dict[str, ApixEventHandler]
    priority_buckets: dict[float, list[str]]
    cached_chain: dict[str, list[str] | None]

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

    def __contains__(self, item):
        return item in self.registry

    @staticmethod
    def _normalise_patterns(
        patterns: Iterable[str],
        *,
        argument_name: str | None = None,
    ) -> list[str]:
        """Validate patterns and remove duplicates without changing order."""
        if isinstance(patterns, str):
            patterns = (patterns,)

        supplied = list(patterns)
        if not supplied:
            raise ValueError(f"{argument_name or 'Patterns'} cannot be empty.")
        if any(
            not isinstance(pattern, str) or not pattern
            for pattern in supplied
        ):
            raise ValueError(
                f"Every pattern in {argument_name or 'patterns'} must be a non-empty string."
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

    def _get_handler_priority(self, handler_name: str) -> float | None:
        """Return the priority of a registered handler, or None if unknown."""
        handler = self.registry.get(handler_name)
        return handler.priority if handler is not None else None

    def _find_handler_position(
        self,
        handler_name: str,
        *,
        priority: float | None = None,
    ) -> tuple[float, int] | None:
        """Return the active bucket and index for a handler name."""
        if priority is not None:
            bucket = self.priority_buckets.get(priority)
            if bucket is None:
                return None
            try:
                return priority, bucket.index(handler_name)
            except ValueError:
                return None

        for prio, bucket in self.priority_buckets.items():
            for index, name in enumerate(bucket):
                if name == handler_name:
                    return prio, index
        return None

    def _validate_between_handlers(
        self,
        between_handlers: tuple[str | None, str | None],
        *,
        handler_name: str,
    ) -> float:
        """Validate boundaries without mutation and return the target priority."""
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
        if handler_name in between_handlers:
            raise ValueError("A handler cannot use itself as an insertion boundary.")
        left_position = (
            self._find_handler_position(
                left_name,
                priority=self._get_handler_priority(left_name),
            )
            if left_name is not None
            else None
        )
        right_position = (
            self._find_handler_position(
                right_name,
                priority=self._get_handler_priority(right_name),
            )
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

            # The right boundary determines the target priority bucket.
            return right_priority

        if left_position is not None:
            return left_position[0]

        assert right_position is not None
        return right_position[0]

    def _invalidate_matching_chains(self, handler: ApixEventHandler) -> None:
        """Expire existing caches accepted by this handler without rebuilding."""
        for event_name in self.cached_chain:
            if self._matches_handler(handler, event_name):
                self.cached_chain[event_name] = None

    def get_handlers_chain_for_event(self, event_name: str) -> list[str]:
        """Return the current chain, rebuilding only absent or expired entries."""
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("event_name must be a non-empty string.")

        chain = self.cached_chain.get(event_name)
        if chain is None:
            chain = []
            for handler_name in self._iter_active_handler_names():
                handler = self.registry.get(handler_name)
                if handler is not None and self._matches_handler(handler, event_name):
                    chain.append(handler_name)
            self.cached_chain[event_name] = chain
        return chain

    def _remove_from_bucket(self, handler_name: str) -> None:
        """Remove a registered name and discard its bucket when empty."""
        position = self._find_handler_position(
            handler_name, 
            priority=self._get_handler_priority(handler_name)
        )
        if position is not None:
            priority, index = position
            bucket = self.priority_buckets[priority]
            bucket.pop(index)
            if not bucket:
                del self.priority_buckets[priority]

    def register_handler(
        self, handler_entry: ApixEventHandler, *, exist_ok: bool = False,
    ) -> None:
        """Validate, then insert or replace an entry and expire affected caches."""
        if not isinstance(handler_entry, ApixEventHandler):
            raise TypeError("handler_entry must be an ApixEventHandler instance.")
        if not handler_entry.name:
            raise ValueError("Handler name cannot be empty.")
        if handler_entry.name in self.registry and not exist_ok:
            raise EventHandlerAlreadyRegisteredError(
                f"Handler `{handler_entry.name}` already registered."
            )
        if not callable(handler_entry.core_func):
            raise TypeError("Handler core_func must be callable.")
        if handler_entry.on_accepted is not None and not callable(handler_entry.on_accepted):
            raise TypeError("Handler on_accepted must be callable.")
        if handler_entry.on_has_error is not None and not callable(handler_entry.on_has_error):
            raise TypeError("Handler on_has_error must be callable.")
        if handler_entry.on_error is not None and not callable(handler_entry.on_error):
            raise TypeError("Handler on_error must be callable.")
        if handler_entry.priority is not None and handler_entry.between_handlers is not None:
            raise ValueError(
                "between_handlers and priority cannot be set together."
            )

        subscriptions = self._normalise_patterns(
            handler_entry.subscribe,
            argument_name="subscribe",
        )
        filters = (
            self._normalise_patterns(handler_entry.filter_event, argument_name="filter_event",)
            if handler_entry.filter_event else []
        )

        between_handlers = handler_entry.between_handlers
        if between_handlers is not None:
            bucket_priority = self._validate_between_handlers(
                between_handlers,
                handler_name=handler_entry.name
            )
        else:
            priority = handler_entry.priority
            if isinstance(priority, bool) or not isinstance(priority, (int, float)):
                raise TypeError(
                    "Handler priority must be a number."
                )
            if not math.isfinite(priority):
                raise ValueError("Handler priority must be finite.")
            bucket_priority = priority

        # Validate first so failed replacements preserve the old registration.
        # Reuse normal unregistration, then insert against the updated bucket.
        self.unregister_handler(handler_entry.name, missing_ok=True)

        handler_entry.subscribe = subscriptions
        handler_entry.filter_event = filters
        handler_entry._register_order = self._register_order
        self.registry[handler_entry.name] = handler_entry
        bucket = self.priority_buckets.setdefault(bucket_priority, [])
        if between_handlers is None:
            bucket.append(handler_entry.name)
        else:
            left_name, right_name = between_handlers
            if right_name is not None:
                insert_index = bucket.index(right_name)
            else:
                if left_name is None:
                    raise ValueError("between_handlers cannot be (None, None).")
                insert_index = bucket.index(left_name) + 1
            bucket.insert(insert_index, handler_entry.name)
        self._invalidate_matching_chains(handler_entry)
        self._register_order += 1

        logger.debug(
            f"Registered handler {handler_entry.name}, "
            f"priority={handler_entry.priority}, "
            f"between_handlers={handler_entry.between_handlers}"
        )

    def unregister_handler(self, handler_name: str, *, missing_ok: bool = False) -> None:
        """Immediately remove an entry and its bucket record, expiring caches."""
        handler = self.registry.get(handler_name)
        if handler is None:
            if not missing_ok:
                raise EventHandlerNotRegisteredError(
                    f"Handler `{handler_name}` not registered."
                )
            return
        self._invalidate_matching_chains(handler)
        self._remove_from_bucket(handler_name)
        del self.registry[handler_name]
        logger.debug(f"Unregistered handler {handler_name}.")

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
    stop_when_error: bool | None = None,
    time_out: float | None = None,
    background: bool | None = None,
):
    """Register an async handler for one or more event-name patterns.

    Handler names are unique across the process-global registry. The decorated
    function or ApixEventHandler instance is returned unchanged. Validation
    happens in register_handler when the returned decorator is applied.

    Event subscription and filtering use case-sensitive
    :func:`fnmatch.fnmatchcase` semantics. The handler chain is resolved lazily
    from the priority buckets when an event is dequeued or the chain is queried.

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
            If ``True``, replace an existing same-name entry with this handler
            and configuration. Validation failures preserve the old registration.

            If ``False``, a duplicate function name raises
            :class:`EventHandlerAlreadyRegisteredError`.

            Uniqueness is based on the handler name, regardless of subscribed
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
            If ``True``, skip this handler's core function when the event has
            upstream errors. Error notifications still run. If ``False``, the
            core may run after notification unless the event is accepted.
            Background-handler failures are logged without changing event errors.

        time_out:
            Maximum execution time in seconds for each invoked core or
            notification function. ``None`` preserves the supplied instance's
            timeout (unlimited for a plain function). Values less than or equal
            to zero explicitly disable the timeout.

        background:
            If ``True``, schedule the handler as a background task without
            waiting for it before dispatching subsequent handlers.

    Dispatch rules:
        1. Each event instance is dispatched in its own task.
        2. Higher-priority buckets dispatch before lower-priority buckets.
        3. Handlers in one bucket retain their explicit or registration order.
        4. ``between_handlers`` determines placement when supplied and cannot
           be combined with an explicit priority.
        5. Candidate names and order are fixed when the event is dequeued.
           Each invocation looks up the current handler and rechecks its
           subscription and filters, skipping missing or nonmatching entries.
           Background tasks check again after waiting for capacity. Calls
           already started continue to completion.
        6. Events with different exact names may dispatch concurrently.
        7. Calling :meth:`ApixEvent.accept` skips subsequent core functions,
           while applicable error and acceptance notifications still run.
        8. Subscription and ordering options replace existing metadata.
           Execution options set to None preserve a supplied instance's settings;
           explicit values override them. Notification functions are preserved.

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
        A decorator that returns the supplied function or handler instance
        unchanged after successful registration or replacement.

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
    def decorator[HandlerT: EventHandlerFunc | ApixEventHandler](
        func: HandlerT,
    ) -> HandlerT:
        handler_name = func.__name__
        # Stage instance metadata separately so a failed replacement cannot
        # mutate an object that is still registered or being executed.
        entry = (
            copy(func) if isinstance(func, ApixEventHandler)
            else ApixEventHandler(func)
        )
        entry.name = handler_name
        entry.subscribe = list(event_names)
        entry.filter_event = filter_event if filter_event is not None else []
        entry.priority = 1 if priority is None and between_handlers is None else priority
        entry.between_handlers = between_handlers
        # Explicit execution options override the supplied instance's settings.
        # None preserves its setting; non-positive timeouts disable its limit.
        if stop_when_error is not None:
            entry.stop_when_error = stop_when_error
        if time_out is not None:
            entry.time_out = time_out if time_out > 0 else None
        if background is not None:
            entry.background = background
        APIX_HANDLER_REGISTRY.register_handler(entry, exist_ok=exist_ok)
        if isinstance(func, ApixEventHandler):
            func.__dict__.update(entry.__dict__)
            APIX_HANDLER_REGISTRY.registry[handler_name] = func
        return func

    return decorator


def unsubscribe(
    handler_name: str,
    *,
    missing_ok: bool = True,
) -> None:
    """Immediately remove a global handler; optionally reject unknown names."""
    APIX_HANDLER_REGISTRY.unregister_handler(handler_name, missing_ok = missing_ok)


def get_handler(
    handler_name: str,
) -> ApixEventHandler | None:
    return APIX_HANDLER_REGISTRY.get_handler(handler_name)


def get_handler_meta(
    handler_name: str,
) -> dict | None:
    handler = APIX_HANDLER_REGISTRY.get_handler(handler_name)
    if handler is None:
        return None
    return {
        'id': handler.id,
        'name': handler.name,
        'register_order': handler._register_order,
        'subscribe': handler.subscribe,
        'filter_event': handler.filter_event,
        'priority': handler.priority,
        'between_handlers': handler.between_handlers,
        'stop_when_error': handler.stop_when_error,
        'time_out': handler.time_out,
        'background': handler.background,
    }


def is_registered(
    handler_name: str,
) -> bool:
    """Return if a handler is registered."""
    return handler_name in APIX_HANDLER_REGISTRY


def get_unmatched_subscriptions(handler_name: str) -> list[str]:
    """Return global handler patterns that matched no observed event name."""
    return APIX_HANDLER_REGISTRY.get_unmatched_subscriptions(handler_name)


__all__ = [
    "ApixHandlerRegistry",
    "APIX_HANDLER_REGISTRY",
    "get_unmatched_subscriptions",
    "subscribe",
    "unsubscribe",
    "get_handler",
    "get_handler_meta",
    "is_registered",
]
