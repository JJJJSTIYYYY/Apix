"""Tests for public event values and handler defaults."""

from apix.core.event.base import EventType, HandlerEntry


async def _handler(event):
    return None


def test_handler_entry_defaults_to_infinite_wait():
    """A directly constructed handler also defaults to no timeout."""
    entry = HandlerEntry(
        id="handler-id",
        name="handler",
        subscribe="event",
        callback=_handler,
        priority=1,
        register_order=0,
    )

    assert entry.time_out == -1
