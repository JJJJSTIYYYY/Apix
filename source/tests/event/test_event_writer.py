"""
Tests for event_writer module.

Covers EventPipeWriter class: post_event, get_event, and clear.
"""

import asyncio
import time
from unittest.mock import patch, AsyncMock

import pytest

from apix.core.event.base import ApixEvent, EventType
from apix.core.event.event_writer import EventPipeWriter


class TestEventPipeWriterPostEvent:
    """Tests for post_event method."""

    @pytest.mark.asyncio
    async def test_post_event_creates_and_puts_event(self):
        """post_event should create an ApixEvent and put it into the pipe."""
        writer = EventPipeWriter()

        # Clear any existing items
        await writer.clear()

        await writer.post_event(
            event_type=EventType.INFO,
            event_name="test.event",
            context={"key": "val"},
        )

        event = await writer.get_event()

        assert isinstance(event, ApixEvent)
        assert event.event_type == EventType.INFO
        assert event.event_name == "test.event"
        assert event.context == {"key": "val"}
        assert isinstance(event.timestamp, float)
        assert event.accepted is False

    @pytest.mark.asyncio
    async def test_post_event_default_context_none(self):
        """post_event with no context should set context to None."""
        writer = EventPipeWriter()
        await writer.clear()

        await writer.post_event(
            event_type=EventType.WARNING,
            event_name="warn.event",
        )

        event = await writer.get_event()
        assert event.context is None

    @pytest.mark.asyncio
    async def test_post_event_timestamp_is_current(self):
        """Timestamp should be close to current time."""
        writer = EventPipeWriter()
        await writer.clear()

        before = time.time()
        await writer.post_event(
            event_type=EventType.INFO,
            event_name="time.event",
        )
        after = time.time()

        event = await writer.get_event()
        assert before <= event.timestamp <= after + 0.01  # small tolerance

    @pytest.mark.asyncio
    async def test_post_event_multiple_events_in_order(self):
        """Multiple events should be retrievable in FIFO order."""
        writer = EventPipeWriter()
        await writer.clear()

        await writer.post_event(
            event_type=EventType.INFO,
            event_name="event.1",
        )
        await writer.post_event(
            event_type=EventType.INFO,
            event_name="event.2",
        )
        await writer.post_event(
            event_type=EventType.ERROR,
            event_name="event.3",
        )

        e1 = await writer.get_event()
        e2 = await writer.get_event()
        e3 = await writer.get_event()

        assert e1.event_name == "event.1"
        assert e2.event_name == "event.2"
        assert e3.event_name == "event.3"
        assert e3.event_type == EventType.ERROR


class TestEventPipeWriterGetEvent:
    """Tests for get_event method."""

    @pytest.mark.asyncio
    async def test_get_event_removes_from_pipe(self):
        """get_event should remove the event from the pipe."""
        writer = EventPipeWriter()
        await writer.clear()

        await writer.post_event(
            event_type=EventType.INFO,
            event_name="test.event",
        )

        # Actually call get_event to remove it
        event = await writer.get_event()
        assert event is not None
        assert event.event_name == "test.event"

        # After get, pipe should be empty
        count = await writer.clear()
        assert count == 0


class TestEventPipeWriterClear:
    """Tests for clear method."""

    @pytest.mark.asyncio
    async def test_clear_empty_pipe_returns_zero(self):
        """Clear on an empty pipe should return 0."""
        writer = EventPipeWriter()
        await writer.clear()  # make sure it's empty

        count = await writer.clear()
        assert count == 0

    @pytest.mark.asyncio
    async def test_clear_removes_all_items(self):
        """Clear should remove all items and return correct count."""
        writer = EventPipeWriter()
        await writer.clear()

        await writer.post_event(
            event_type=EventType.INFO,
            event_name="e1",
        )
        await writer.post_event(
            event_type=EventType.INFO,
            event_name="e2",
        )
        await writer.post_event(
            event_type=EventType.INFO,
            event_name="e3",
        )

        count = await writer.clear()
        assert count == 3

        # Verify pipe is empty
        count2 = await writer.clear()
        assert count2 == 0

    @pytest.mark.asyncio
    async def test_clear_partial_then_get(self):
        """After a partial clear, remaining items should be retrievable."""
        writer = EventPipeWriter()
        await writer.clear()

        await writer.post_event(
            event_type=EventType.INFO,
            event_name="keep",
        )
        await writer.post_event(
            event_type=EventType.INFO,
            event_name="discard",
        )

        # Get only one, leave the other
        e = await writer.get_event()
        assert e.event_name == "keep"

        count = await writer.clear()
        assert count == 1


class TestEventPipeWriterSingleton:
    """Tests for the module-level event_pipe_writer singleton."""

    def test_event_pipe_is_EventPipeWriter_instance(self):
        """Module-level event_pipe_writer should be an EventPipeWriter instance."""
        from apix.core.event.event_writer import event_pipe_writer

        assert isinstance(event_pipe_writer, EventPipeWriter)

    def test_event_pipe_singleton_same_instance(self):
        """Multiple imports should return the same event_pipe_writer instance."""
        from apix.core.event.event_writer import event_pipe_writer as ep1
        from apix.core.event.event_writer import event_pipe_writer as ep2

        assert ep1 is ep2
