"""Process-local registry of exact event names observed at runtime."""

from threading import RLock

from apix.core.event.base import ApixEvent


class ApixEventRegistry:
    """Store exact event names observed by the local event runtime.

    The registry is observational only: it does not own queued events or
    control handler dispatch. Event names are stored instead of
    :class:`ApixEvent` instances because event objects are mutable and
    unhashable. Exact names can be used for diagnostics, subscription analysis,
    and wildcard handler-chain cache prewarming.

    The class is a process-local singleton. All reads and writes are protected
    by a reentrant lock so event publication and handler registration may query
    the registry safely from different threads.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._registered_events: set[str] = set()
        self._lock = RLock()
        self._initialized = True

    def record_event(self, event: ApixEvent) -> None:
        """Record the exact name of one published event.

        Repeated publication of the same event name has no additional effect.

        Args:
            event: Published event whose exact name should be recorded.

        Raises:
            TypeError: If ``event`` is not an :class:`ApixEvent`.
            ValueError: If the event name is empty.
        """
        if not isinstance(event, ApixEvent):
            raise TypeError("event must be an ApixEvent instance.")
        if not event.event_name:
            raise ValueError("event.event_name must be a non-empty string.")

        with self._lock:
            self._registered_events.add(event.event_name)

    def get_registered_events(self) -> frozenset[str]:
        """Return an immutable snapshot of exact event names seen at runtime."""
        with self._lock:
            return frozenset(self._registered_events)

    def clear(self) -> None:
        """Forget every observed event name without affecting queued events."""
        with self._lock:
            self._registered_events.clear()


apix_event_registry = ApixEventRegistry()


__all__ = ["ApixEventRegistry", "apix_event_registry"]
