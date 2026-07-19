"""
Tests for event_loop module.

Covers ApixEventLoop: start/stop lifecycle, event consumption,
dispatch logic, background handlers, error handling, and timeouts.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apix.core.event.base import ApixEvent, EventType, HandlerEntry
from apix.core.event.event_registry import ApixEventRegistry
from apix.core.event.event_loop import ApixEventLoop


# ============================
# Helpers
# ============================


def _reset_registry(registry: ApixEventRegistry):
    """Reset registry to clean state."""
    registry._handlers.clear()
    registry._handlers_meta.clear()
    registry._register_order = 0


def _make_handler_entry(
    name="test_handler",
    subscribe="test.event",
    callback=None,
    priority=1.0,
    register_order=0,
    stop_when_error=True,
    time_out=30.0,
    background=False,
):
    """Create a HandlerEntry."""
    if callback is None:
        callback = AsyncMock()

    return HandlerEntry(
        id=f"id_{name}",
        name=name,
        subscribe=subscribe,
        callback=callback,
        priority=priority,
        register_order=register_order,
        stop_when_error=stop_when_error,
        time_out=time_out,
        background=background,
    )


def _make_event(event_name="test.event", accepted=False):
    """Create a test ApixEvent."""
    return ApixEvent(
        event_id="event-"+uuid4().hex,
        event_type=EventType.INFO,
        event_name=event_name,
        context=None,
        timestamp=0.0,
        accepted=accepted,
    )


# ============================
# Tests: start / stop
# ============================


class TestStartStop:
    """Tests for start() and stop() lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_consumer_task(self):
        """start() should create a consumer asyncio.Task."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        with patch.object(
            handler, "_event_consumer_loop", AsyncMock()
        ) as mock_loop:
            await handler.start()
            assert handler._event_consumer_task is not None
            mock_loop.assert_called_once()

        await handler.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Calling start() multiple times should not create multiple tasks."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        with patch.object(handler, "_event_consumer_loop", AsyncMock()):
            await handler.start()
            task1 = handler._event_consumer_task
            await handler.start()
            task2 = handler._event_consumer_task
            assert task1 is task2

        await handler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_consumer_task(self):
        """stop() should cancel the consumer task."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def block_forever():
            try:
                while True:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise

        handler._event_consumer_loop = block_forever
        await handler.start()
        assert handler._event_consumer_task is not None

        await handler.stop()
        assert handler._event_consumer_task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_safe(self):
        """Calling stop() when not started should not raise."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        await handler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_dispatch_tasks(self):
        """stop() should cancel pending dispatch tasks."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def slow_dispatch():
            await asyncio.sleep(10)

        task = asyncio.create_task(slow_dispatch())
        handler._dispatch_tasks.add(task)

        await handler.stop()
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_tasks(self):
        """stop() should cancel pending background handler tasks."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def slow_background():
            await asyncio.sleep(10)

        task = asyncio.create_task(slow_background())
        handler._background_handler_tasks.add(task)

        await handler.stop()
        assert task.cancelled() or task.done()


# ============================
# Tests: _dispatch_event
# ============================


class TestDispatchEvent:
    """Tests for _dispatch_event method."""

    @pytest.mark.asyncio
    async def test_dispatch_empty_event_name_returns_none(self):
        """Event with empty event_name should return None."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        event = _make_event(event_name="")
        result = await handler._dispatch_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_no_handlers_returns_event(self):
        """
        When no handlers are registered, event is returned as-is.
        Note: the code returns early without calling event.accept()
        when handlers list is empty (see _dispatch_event line 189-190).
        """
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        event = _make_event()
        result = await handler._dispatch_event(event)
        assert result is event
        # Early return skips accept() - the event keeps its original accepted state
        assert result.accepted is False

    @pytest.mark.asyncio
    async def test_dispatch_calls_handler(self):
        """Registered handler should be called with the event."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        mock_callback = AsyncMock()
        entry = _make_handler_entry(callback=mock_callback)
        registry._handlers["test.event"] = [entry]

        event = _make_event()
        result = await handler._dispatch_event(event)

        mock_callback.assert_awaited_once_with(event)
        assert result.accepted is True

    @pytest.mark.asyncio
    async def test_dispatch_multiple_handlers_called_in_order(self):
        """Multiple handlers should be called in registry order."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        call_order = []

        async def h1(event):
            call_order.append("h1")

        async def h2(event):
            call_order.append("h2")

        entry1 = _make_handler_entry(name="h1", callback=h1, priority=10.0)
        entry2 = _make_handler_entry(name="h2", callback=h2, priority=5.0)
        registry._handlers["test.event"] = [entry1, entry2]

        event = _make_event()
        await handler._dispatch_event(event)

        assert call_order == ["h1", "h2"]

    @pytest.mark.asyncio
    async def test_dispatch_event_accepted_stops_iteration(self):
        """When event.accepted is True, remaining handlers are skipped."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        called = []

        async def h1(event):
            called.append("h1")
            event.accept()

        async def h2(event):
            called.append("h2")

        entry1 = _make_handler_entry(name="h1", callback=h1, priority=10.0)
        entry2 = _make_handler_entry(name="h2", callback=h2, priority=5.0)
        registry._handlers["test.event"] = [entry1, entry2]

        event = _make_event()
        await handler._dispatch_event(event)

        assert called == ["h1"]

    @pytest.mark.asyncio
    async def test_dispatch_event_already_accepted_skips_all(self):
        """If event is already accepted, no handlers are called."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        mock_callback = AsyncMock()
        entry = _make_handler_entry(callback=mock_callback)
        registry._handlers["test.event"] = [entry]

        event = _make_event(accepted=True)
        result = await handler._dispatch_event(event)

        mock_callback.assert_not_awaited()
        assert result.accepted is True

    @pytest.mark.asyncio
    async def test_dispatch_handler_timeout_logs_error(self):
        """Handler timeout should log an error and continue."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def slow_handler(event):
            await asyncio.sleep(10)

        entry = _make_handler_entry(callback=slow_handler, time_out=0.001)
        registry._handlers["test.event"] = [entry]

        event = _make_event()

        with patch("apix.core.event.event_loop.logger") as mock_logger:
            result = await handler._dispatch_event(event)

            error_calls = [
                c for c in mock_logger.error.call_args_list
                if "timeout" in str(c).lower()
            ]
            assert len(error_calls) >= 1
            assert result.accepted is True

    @pytest.mark.asyncio
    async def test_dispatch_handler_exception_logs_error(self):
        """Handler exception should log an error."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def failing_handler(event):
            raise ValueError("test error")

        entry = _make_handler_entry(callback=failing_handler)
        registry._handlers["test.event"] = [entry]

        event = _make_event()

        with patch("apix.core.event.event_loop.logger") as mock_logger:
            result = await handler._dispatch_event(event)
            assert result.accepted is True
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_handler_stop_when_error_true_breaks(self):
        """stop_when_error=True should stop dispatching on handler error."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        called = []

        async def h1(event):
            called.append("h1")
            raise ValueError("error")

        async def h2(event):
            called.append("h2")

        entry1 = _make_handler_entry(name="h1", callback=h1, stop_when_error=True)
        entry2 = _make_handler_entry(name="h2", callback=h2, stop_when_error=False)
        registry._handlers["test.event"] = [entry1, entry2]

        event = _make_event()

        with patch("apix.core.event.event_loop.logger"):
            await handler._dispatch_event(event)

        assert called == ["h1"]

    @pytest.mark.asyncio
    async def test_dispatch_handler_stop_when_error_false_continues(self):
        """stop_when_error=False should continue dispatching after error."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        called = []

        async def h1(event):
            called.append("h1")
            raise ValueError("error")

        async def h2(event):
            called.append("h2")

        entry1 = _make_handler_entry(name="h1", callback=h1, stop_when_error=False)
        entry2 = _make_handler_entry(name="h2", callback=h2, stop_when_error=False)
        registry._handlers["test.event"] = [entry1, entry2]

        event = _make_event()

        with patch("apix.core.event.event_loop.logger"):
            await handler._dispatch_event(event)

        assert called == ["h1", "h2"]

    @pytest.mark.asyncio
    async def test_dispatch_background_handler_creates_task(self):
        """Background handlers should create background tasks."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def bg_handler(event):
            await asyncio.sleep(0.01)

        entry = _make_handler_entry(callback=bg_handler, background=True)
        registry._handlers["test.event"] = [entry]

        event = _make_event()

        result = await handler._dispatch_event(event)
        assert result.accepted is True

        # Allow a short time for background task to complete
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_dispatch_semaphore_release_on_error(self):
        """Semaphore should be released even when dispatch fails."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        # Use patch.object to ensure proper cleanup (registry is a singleton)
        mock_get_handlers = MagicMock(side_effect=RuntimeError("fatal error"))
        with patch.object(registry, "get_handlers", mock_get_handlers):
            event = _make_event()
            with patch("apix.core.event.event_loop.logger"):
                await handler._dispatch_event(event)

        # Semaphore should be released (no deadlock)
        await handler._dispatch_semaphore.acquire()
        handler._dispatch_semaphore.release()


# ============================
# Tests: _run_background_handler
# ============================


class TestRunBackgroundHandler:
    """Tests for _run_background_handler method."""

    @pytest.mark.asyncio
    async def test_background_handler_no_timeout(self):
        """Background handler with time_out=-1 should run normally."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        mock_callback = AsyncMock()
        entry = _make_handler_entry(callback=mock_callback, time_out=-1)
        event = _make_event()

        await handler._run_background_handler(entry, event)
        mock_callback.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_background_handler_with_timeout(self):
        """Background handler with a timeout should use wait_for."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        mock_callback = AsyncMock()
        entry = _make_handler_entry(callback=mock_callback, time_out=5.0)
        event = _make_event()

        await handler._run_background_handler(entry, event)
        mock_callback.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_background_handler_timeout_error(self):
        """Background handler timeout should log error."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def slow_handler(event):
            await asyncio.sleep(10)

        entry = _make_handler_entry(callback=slow_handler, time_out=0.001)
        event = _make_event()

        with patch("apix.core.event.event_loop.logger") as mock_logger:
            await handler._run_background_handler(entry, event)
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_background_handler_cancelled_error_propagates(self):
        """CancelledError should be re-raised in background handler."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def cancelled_handler(event):
            raise asyncio.CancelledError()

        entry = _make_handler_entry(callback=cancelled_handler)
        event = _make_event()

        with pytest.raises(asyncio.CancelledError):
            await handler._run_background_handler(entry, event)

    @pytest.mark.asyncio
    async def test_background_handler_exception_logs(self):
        """Background handler exception should be logged."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        async def error_handler(event):
            raise ValueError("background error")

        entry = _make_handler_entry(callback=error_handler)
        event = _make_event()

        with patch("apix.core.event.event_loop.logger") as mock_logger:
            await handler._run_background_handler(entry, event)
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_background_handler_semaphore_used(self):
        """Background handler should acquire the semaphore."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        mock_callback = AsyncMock()
        entry = _make_handler_entry(callback=mock_callback, time_out=-1)
        event = _make_event()

        await handler._run_background_handler(entry, event)

        await handler._background_handler_semaphore.acquire()
        handler._background_handler_semaphore.release()


# ============================
# Tests: _create_background_handler_task
# ============================


class TestCreateBackgroundHandlerTask:
    """Tests for _create_background_handler_task method."""

    @pytest.mark.asyncio
    async def test_creates_task_adds_to_set(self):
        """Should create a task and add it to _background_handler_tasks."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        mock_callback = AsyncMock()
        entry = _make_handler_entry(callback=mock_callback, time_out=-1)
        event = _make_event()

        initial_count = len(handler._background_handler_tasks)
        handler._create_background_handler_task(entry, event)

        assert len(handler._background_handler_tasks) == initial_count + 1

        # Wait for task to complete
        pending = list(handler._background_handler_tasks)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        mock_callback.assert_awaited_once_with(event)


# ============================
# Tests: Consumer Loop
# ============================


class TestEventConsumerLoop:
    """Integration tests for the event dispatch flow."""

    @pytest.mark.asyncio
    async def test_consumer_dispatch_flow(self):
        """End-to-end: event -> dispatch -> handler called -> accepted."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        mock_callback = AsyncMock()
        entry = _make_handler_entry(callback=mock_callback)
        registry._handlers["test.event"] = [entry]

        event = _make_event()
        result = await handler._dispatch_event(event)

        assert result is not None
        assert result.accepted
        mock_callback.assert_awaited_once_with(event)


# ============================
# Tests: Constructor
# ============================


class TestConstructor:
    """Tests for ApixEventLoop.__init__."""

    def test_init_stores_registry(self):
        """Constructor should store the registry reference."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)
        assert handler._registry is registry

    def test_init_initial_state(self):
        """Initial state should have correct defaults."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        handler = ApixEventLoop(registry)

        assert handler._event_consumer_task is None
        assert isinstance(handler._dispatch_tasks, set)
        assert len(handler._dispatch_tasks) == 0
        assert isinstance(handler._background_handler_tasks, set)
        assert len(handler._background_handler_tasks) == 0


# ============================
# Tests: Module-level singleton
# ============================


class TestModuleSingleton:
    """Tests for the module-level apix_event_loop."""

    def test_pipe_event_handler_is_PipeEventHandler_instance(self):
        """Module-level apix_event_loop should be a ApixEventLoop."""
        from apix.core.event.event_loop import apix_event_loop

        assert isinstance(apix_event_loop, ApixEventLoop)
