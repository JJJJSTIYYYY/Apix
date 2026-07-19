"""
Tests for event_pipe_writer module.

The module provides a global asyncio.Queue instance (EVENT_PIPE)
used for inter-module event transport.
"""

import asyncio

import pytest


class TestEventPipe:
    """Tests for the EVENT_PIPE asyncio.Queue."""

    def test_event_pipe_is_asyncio_queue(self):
        """EVENT_PIPE should be an asyncio.Queue instance."""
        from apix.core.event.event_pipe import EVENT_PIPE

        assert isinstance(EVENT_PIPE, asyncio.Queue)

    def test_event_pipe_has_valid_maxsize(self):
        """EVENT_PIPE maxsize should be a positive integer."""
        from apix.core.event.event_pipe import EVENT_PIPE

        assert EVENT_PIPE.maxsize > 0
        assert isinstance(EVENT_PIPE.maxsize, int)

    @pytest.mark.asyncio
    async def test_event_pipe_put_and_get(self):
        """Events can be put into and retrieved from EVENT_PIPE."""
        from apix.core.event.event_pipe import EVENT_PIPE

        # Ensure pipe is empty at start
        while not EVENT_PIPE.empty():
            EVENT_PIPE.get_nowait()

        await EVENT_PIPE.put("event_1")
        await EVENT_PIPE.put("event_2")

        assert EVENT_PIPE.qsize() == 2

        item1 = await EVENT_PIPE.get()
        item2 = await EVENT_PIPE.get()

        assert item1 == "event_1"
        assert item2 == "event_2"

    @pytest.mark.asyncio
    async def test_event_pipe_empty(self):
        """EVENT_PIPE.empty() should reflect the queue state."""
        from apix.core.event.event_pipe import EVENT_PIPE

        # Drain pipe first
        while not EVENT_PIPE.empty():
            EVENT_PIPE.get_nowait()

        assert EVENT_PIPE.empty() is True

        await EVENT_PIPE.put("event")

        assert EVENT_PIPE.empty() is False

        await EVENT_PIPE.get()

        assert EVENT_PIPE.empty() is True

    def test_event_pipe_module_import_safety(self):
        """EVENT_PIPE should be importable as a module-level singleton."""
        from apix.core.event.event_pipe import EVENT_PIPE

        # Second import should return the same object
        from apix.core.event.event_pipe import EVENT_PIPE as EVENT_PIPE_2

        assert EVENT_PIPE is EVENT_PIPE_2
