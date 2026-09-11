"""Behavioral contracts for upstream notifications and failure isolation."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from apix.core.event import ApixEvent, ApixEventError, ApixEventHandler, EventType
from apix.core.event.event_pipe import encode_event, event_from_payload
from apix.core.event.event_loop import ApixEventLoop
from apix.core.event.handler_registry import (
    APIX_HANDLER_REGISTRY,
    get_handler_meta,
    subscribe,
)


def make_event(*, has_error=False, accepted=False):
    event = ApixEvent("test-id", EventType.WORKFLOW, "contract.event", None, 0)
    event.accepted = accepted
    if has_error:
        event.error_stack.append(ApixEventError(
            "upstream", "core_func", "ValueError", "upstream failure", "traceback",
        ))
    return event


@pytest.mark.parametrize("has_error", [False, True])
@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize("stop_when_error", [False, True])
async def test_execution_state_matrix(has_error, accepted, stop_when_error):
    calls = []

    async def core(event):
        calls.append("core")

    async def on_error(event):
        calls.append("error")

    async def on_accepted(event):
        calls.append("accepted")

    handler = ApixEventHandler(core, on_accepted, on_error,
                               stop_when_error=stop_when_error)
    event = make_event(has_error=has_error, accepted=accepted)
    await handler.execute(event)
    expected = ["error"] if has_error else []
    if accepted:
        expected.append("accepted")
    elif not (has_error and stop_when_error):
        expected.append("core")
    assert calls == expected


async def test_own_core_failure_never_calls_own_error_notification():
    async def core(event):
        raise ValueError("own failure")

    own_notification = AsyncMock()
    event = make_event()
    handler = ApixEventHandler(core, on_has_error=own_notification)
    await handler(event)
    own_notification.assert_not_awaited()
    assert event.has_error
    [error] = event.error_stack
    assert error.handler_name == "core"
    assert error.phase == "core_func"
    assert error.exception_type == "ValueError"
    assert error.message == "own failure"
    assert 'raise ValueError("own failure")' in error.traceback
    assert not event.accepted


async def test_core_handles_its_own_recovery_without_event_error():
    async def core(event):
        try:
            raise ValueError("handled locally")
        except ValueError:
            event.context = "recovered"

    event = make_event()
    await ApixEventHandler(core)(event)
    assert event.context == "recovered"
    assert not event.has_error


async def test_broken_notifications_are_recorded_once_and_do_not_stop_chain():
    calls = []

    async def on_error(event):
        calls.append("error")
        raise RuntimeError("error notification failed")

    async def on_accepted(event):
        calls.append("accepted")
        raise LookupError("acceptance notification failed")

    core = AsyncMock()
    event = make_event(has_error=True, accepted=True)
    await ApixEventHandler(core, on_accepted, on_error)(event)
    later = AsyncMock()
    await ApixEventHandler(core, on_has_error=later)(event)
    assert calls == ["error", "accepted"]
    assert [error.phase for error in event.error_stack] == [
        "core_func", "on_has_error", "on_accepted",
    ]
    core.assert_not_awaited()
    later.assert_awaited_once_with(event)


async def test_error_notification_may_accept_event_before_core():
    async def on_error(event):
        event.accept()

    core, accepted = AsyncMock(), AsyncMock()
    event = make_event(has_error=True)
    await ApixEventHandler(core, accepted, on_error, stop_when_error=False)(event)
    core.assert_not_awaited()
    accepted.assert_awaited_once_with(event)


async def test_repeated_core_failure_does_not_repeat_upstream_notification():
    core = AsyncMock(side_effect=RuntimeError("own failure"))
    notified = AsyncMock()
    event = make_event(has_error=True)
    await ApixEventHandler(core, on_has_error=notified, stop_when_error=False)(event)
    notified.assert_awaited_once_with(event)
    assert len(event.error_stack) == 2


@pytest.mark.parametrize("phase", ["core_func", "on_has_error", "on_accepted"])
@pytest.mark.parametrize("background", [False, True])
async def test_timeout_is_per_phase_and_background_errors_are_log_only(phase, background):
    cleaned = asyncio.Event()

    async def blocked(event):
        try:
            await asyncio.Future()
        finally:
            cleaned.set()

    core = AsyncMock()
    callbacks = {"core_func": core, phase: blocked}
    handler = ApixEventHandler(**callbacks, time_out=0.01, background=background)
    event = make_event(has_error=phase == "on_has_error", accepted=phase == "on_accepted")
    before = list(event.error_stack)
    with patch("apix.core.event.base.logger") as logger:
        await handler(event)
    assert cleaned.is_set()
    logger.error.assert_called_once()
    if background:
        assert event.error_stack == before
    else:
        assert len(event.error_stack) == len(before) + 1
        assert event.error_stack[-1].phase == phase
        assert event.error_stack[-1].exception_type == "TimeoutError"


@pytest.mark.parametrize("phase", ["core_func", "on_has_error", "on_accepted"])
async def test_cancellation_propagates_without_recording_an_error(phase):
    async def cancelled(event):
        raise asyncio.CancelledError()

    event = make_event(has_error=phase == "on_has_error", accepted=phase == "on_accepted")
    before = list(event.error_stack)
    handler = ApixEventHandler(**{"core_func": AsyncMock(), phase: cancelled})
    with pytest.raises(asyncio.CancelledError):
        await handler(event)
    assert event.error_stack == before


async def test_error_stack_round_trip_and_instance_isolation():
    async def failing(event):
        raise RuntimeError("serializable failure")

    event = make_event()
    await ApixEventHandler(failing)(event)
    restored = event_from_payload(encode_event(event))
    assert restored.error_stack == event.error_stack
    assert restored.has_error
    assert restored.error_stack is not event.error_stack
    assert not make_event().has_error


@pytest.fixture
def registry():
    registry = APIX_HANDLER_REGISTRY
    registry.registry.clear()
    registry.priority_buckets.clear()
    registry.cached_chain.clear()
    registry._register_order = 0
    yield registry
    registry.registry.clear()
    registry.priority_buckets.clear()
    registry.cached_chain.clear()
    registry._register_order = 0


@pytest.mark.parametrize("use_defaults", [False, True])
async def test_subscribe_decorates_callable_handler_and_overrides_options(registry, use_defaults):
    async def core(event):
        event.context = "called"

    notification = AsyncMock()
    handler = ApixEventHandler(core, on_has_error=notification,
                               stop_when_error=False, time_out=42, background=True)
    options = {} if use_defaults else {"stop_when_error": True, "time_out": 3, "background": False}
    decorated = subscribe("contract.*", priority=8, **options)(handler)
    assert decorated is handler
    assert registry.get_handler("core") is handler
    assert handler.__name__ == "core"
    assert handler.on_has_error is notification
    assert handler.stop_when_error is (False if use_defaults else True)
    assert handler.time_out == (42 if use_defaults else 3)
    assert handler.background is (True if use_defaults else False)
    assert handler._register_order == 0
    assert handler.priority == 8
    assert handler.subscribe == ["contract.*"]
    assert not hasattr(handler, "register_order")
    assert get_handler_meta("missing") is None
    event = make_event()
    await decorated(event)
    assert event.context == "called"


async def test_subscribe_duplicate_replaces_registered_instance_options(registry):
    async def core(event):
        pass

    handler = subscribe("contract.*", background=True)(ApixEventHandler(core))
    subscribe("other.*", background=False)(handler)
    assert handler.background is False
    assert handler.subscribe == ["other.*"]
    assert registry._register_order == 2


async def test_dispatch_notifies_all_later_handlers_after_failure_and_acceptance(registry):
    calls = []

    @subscribe("contract.*", priority=10)
    async def first(event):
        event.accept()
        raise ValueError("upstream failed after acceptance")

    async def core(event):
        pytest.fail("An accepted event must not execute another core")

    async def notify_error(event):
        calls.append("error")

    async def notify_accepted(event):
        calls.append("accepted")

    for index in range(3):
        handler = ApixEventHandler(core, notify_accepted, notify_error)
        handler.name = f"later_{index}"
        subscribe("contract.*")(handler)
    event = make_event()
    await ApixEventLoop(registry)._dispatch_event(
        event,
        registry.get_handlers_chain_for_event(event.event_name),
    )
    assert calls == ["error", "accepted"] * 3
    assert len(event.error_stack) == 1


async def test_background_failure_before_next_core_is_still_log_only(registry):
    background_started = asyncio.Event()
    core_ran = asyncio.Event()

    @subscribe("contract.*", priority=10, background=True)
    async def background(event):
        background_started.set()
        raise ValueError("background failure")

    @subscribe("contract.*", priority=5)
    async def wait_for_background(event):
        await background_started.wait()

    async def last(event):
        core_ran.set()

    notified = AsyncMock()
    subscribe("contract.*")(ApixEventHandler(last, on_has_error=notified))
    loop = ApixEventLoop(registry)
    event = make_event()
    with patch("apix.core.event.base.logger") as logger:
        await asyncio.wait_for(loop._dispatch_event(event, loop._registry.get_handlers_chain_for_event(event.event_name) if event.event_name else []), 1)
        await asyncio.gather(*loop._background_handler_tasks)
    assert core_ran.is_set()
    assert not event.has_error
    assert not event.accepted
    notified.assert_not_awaited()
    logger.error.assert_called_once()


async def test_background_handler_checks_acceptance_when_it_starts(registry):
    core, accepted = AsyncMock(), AsyncMock()
    handler = ApixEventHandler(core, on_accepted=accepted)
    handler.name = "background"
    subscribe("contract.*", priority=10, background=True)(handler)

    @subscribe("contract.*")
    async def accept(event):
        event.accept()

    loop = ApixEventLoop(registry)
    event = make_event()
    await loop._dispatch_event(
        event,
        loop._registry.get_handlers_chain_for_event(event.event_name) if event.event_name else [],
    )
    await asyncio.gather(*loop._background_handler_tasks)
    core.assert_not_awaited()
    accepted.assert_awaited_once_with(event)


@pytest.mark.parametrize("phase", ["core_func", "on_has_error", "on_accepted"])
@pytest.mark.parametrize("background", [False, True])
async def test_on_error_receives_own_original_exception(phase, background):
    error = ValueError("own execution failed")
    observed = []

    async def failing(event):
        raise error

    async def on_error(event, exc):
        observed.append((event, exc, list(event.error_stack)))

    callbacks = {"core_func": AsyncMock(), phase: failing}
    handler = ApixEventHandler(**callbacks, on_error=on_error, background=background)
    event = make_event(has_error=phase == "on_has_error", accepted=phase == "on_accepted")
    before = list(event.error_stack)
    await handler(event)
    assert len(observed) == 1
    assert observed[0][0] is event
    assert observed[0][1] is error
    if background:
        assert observed[0][2] == before == event.error_stack
    else:
        assert observed[0][2] == event.error_stack
        assert event.error_stack[-1].phase == phase
        assert len(event.error_stack) == len(before) + 1


async def test_upstream_error_alone_does_not_call_on_error():
    own_error, upstream_error, core = AsyncMock(), AsyncMock(), AsyncMock()
    event = make_event(has_error=True)
    await ApixEventHandler(core, on_has_error=upstream_error, on_error=own_error)(event)
    upstream_error.assert_awaited_once_with(event)
    own_error.assert_not_awaited()
    core.assert_not_awaited()


@pytest.mark.parametrize("background", [False, True])
@pytest.mark.parametrize("hook_failure", ["exception", "timeout"])
async def test_failing_on_error_is_not_called_recursively(background, hook_failure):
    calls = []

    async def core(event):
        raise ValueError("core failure")

    async def on_error(event, exc):
        calls.append(exc)
        if hook_failure == "timeout":
            await asyncio.Future()
        raise RuntimeError("error hook failure")

    event = make_event()
    handler = ApixEventHandler(core, on_error=on_error, background=background, time_out=0.01)
    with patch("apix.core.event.base.logger") as logger:
        await handler(event)
    assert len(calls) == 1
    assert isinstance(calls[0], ValueError)
    assert logger.error.call_count == 2
    if background:
        assert not event.has_error
    else:
        assert [item.phase for item in event.error_stack] == ["core_func", "on_error"]
        assert event.error_stack[-1].exception_type == ("TimeoutError" if hook_failure == "timeout" else "RuntimeError")
        restored = event_from_payload(encode_event(event))
        assert restored.error_stack == event.error_stack


async def test_on_error_receives_timeout_after_core_cleanup():
    cleaned = asyncio.Event()
    observed = []

    async def core(event):
        try:
            await asyncio.Future()
        finally:
            cleaned.set()

    async def on_error(event, exc):
        assert cleaned.is_set()
        observed.append(exc)

    event = make_event()
    await ApixEventHandler(core, on_error=on_error, time_out=0.01)(event)
    assert len(observed) == 1
    assert isinstance(observed[0], TimeoutError)


async def test_on_error_cancellation_propagates_without_error_record():
    async def on_error(event, exc):
        raise asyncio.CancelledError()

    event = make_event()
    handler = ApixEventHandler(AsyncMock(side_effect=ValueError("core failure")), on_error=on_error)
    with pytest.raises(asyncio.CancelledError):
        await handler(event)
    assert [error.phase for error in event.error_stack] == ["core_func"]


async def test_external_cancellation_does_not_call_on_error():
    started = asyncio.Event()

    async def core(event):
        started.set()
        await asyncio.Future()

    on_error = AsyncMock()
    event = make_event()
    task = asyncio.create_task(ApixEventHandler(core, on_error=on_error)(event))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    on_error.assert_not_awaited()
    assert not event.has_error


async def test_subscribe_preserves_on_error_and_later_handler_observes_failure(registry):
    calls = []
    original = ValueError("own failure")

    async def core(event):
        raise original

    async def on_error(event, exc):
        assert exc is original
        calls.append("own error")

    handler = ApixEventHandler(core, on_error=on_error)
    assert subscribe("contract.*", priority=10)(handler) is handler
    assert handler.on_error is on_error

    async def later_core(event):
        calls.append("later core")

    async def upstream_error(event):
        calls.append("upstream error")
        assert event.error_stack[0].message == "own failure"

    subscribe("contract.*")(ApixEventHandler(later_core, on_has_error=upstream_error))
    await ApixEventLoop(registry)._dispatch_event(make_event(), registry.get_handlers_chain_for_event("contract.event"))
    assert calls == ["own error", "upstream error"]


async def test_on_error_acceptance_still_allows_remaining_notifications():
    calls = []

    async def upstream_error(event):
        raise ValueError("notification failed")

    async def on_error(event, exc):
        calls.append("own error")
        event.accept()

    async def accepted(event):
        calls.append("accepted")

    core = AsyncMock()
    event = make_event(has_error=True)
    await ApixEventHandler(core, accepted, upstream_error, on_error, stop_when_error=False)(event)
    assert calls == ["own error", "accepted"]
    core.assert_not_awaited()
