"""Tests for the registry of exact event names observed at runtime."""

import time
from unittest.mock import AsyncMock

import pytest

import apix.core.event as event_package
from apix.core.event.base import ApixEvent, EventType
from apix.core.event.event_pipe import ApixEventPipe
from apix.core.event.event_registry import (
    ApixEventRegistry,
    APIX_EVENT_REGISTRY,
)


def make_event(event_name: str) -> ApixEvent:
    """Create one event for registry tests."""
    return ApixEvent(
        event_id=f"event-{event_name}",
        event_type=EventType.WORKFLOW,
        event_name=event_name,
        context=None,
        timestamp=time.time(),
    )


def test_event_registry_class_and_singleton_are_exported():
    assert event_package.ApixEventRegistry is ApixEventRegistry
    assert event_package.APIX_EVENT_REGISTRY is APIX_EVENT_REGISTRY
    assert ApixEventRegistry() is APIX_EVENT_REGISTRY
    assert not hasattr(event_package, "EVENT_REGISTRY")
    assert not hasattr(event_package, "record_event")
    assert not hasattr(event_package, "get_registered_events")


def test_record_event_stores_exact_case_sensitive_names_once():
    APIX_EVENT_REGISTRY.record_event(make_event("Graph.Start"))
    APIX_EVENT_REGISTRY.record_event(make_event("Graph.Start"))
    APIX_EVENT_REGISTRY.record_event(make_event("graph.start"))

    assert APIX_EVENT_REGISTRY.get_registered_events() == frozenset(
        {"Graph.Start", "graph.start"}
    )


def test_get_registered_events_returns_immutable_snapshot():
    APIX_EVENT_REGISTRY.record_event(make_event("event.one"))
    snapshot = APIX_EVENT_REGISTRY.get_registered_events()
    APIX_EVENT_REGISTRY.record_event(make_event("event.two"))

    assert snapshot == frozenset({"event.one"})
    assert APIX_EVENT_REGISTRY.get_registered_events() == frozenset(
        {"event.one", "event.two"}
    )


def test_clear_forgets_observed_names():
    APIX_EVENT_REGISTRY.record_event(make_event("event.one"))

    APIX_EVENT_REGISTRY.clear()

    assert APIX_EVENT_REGISTRY.get_registered_events() == frozenset()


def test_record_event_validates_input():
    with pytest.raises(TypeError, match="ApixEvent"):
        APIX_EVENT_REGISTRY.record_event(object())
    with pytest.raises(ValueError, match="event_name"):
        APIX_EVENT_REGISTRY.record_event(make_event(""))


@pytest.mark.asyncio
async def test_post_event_records_name_before_builtin_dispatch():
    pipe = ApixEventPipe(remote_enabled=False)

    await pipe.post_event(
        event_type=EventType.INFO,
        event_name="runtime.posted",
    )

    assert APIX_EVENT_REGISTRY.get_registered_events() == frozenset(
        {"runtime.posted"}
    )
    await pipe.get()
    pipe.task_done()


def test_put_nowait_records_apix_events_but_ignores_other_queue_values():
    pipe = ApixEventPipe(remote_enabled=False)

    pipe.put_nowait(make_event("runtime.nowait"))
    pipe.put_nowait("raw-value")

    assert APIX_EVENT_REGISTRY.get_registered_events() == frozenset(
        {"runtime.nowait"}
    )
    assert pipe.get_nowait().event_name == "runtime.nowait"
    pipe.task_done()
    assert pipe.get_nowait() == "raw-value"
    pipe.task_done()


@pytest.mark.asyncio
async def test_mailtruck_publish_records_name_after_success():
    mailtruck = AsyncMock()
    pipe = ApixEventPipe(
        remote_enabled=False,
        mailtruck=mailtruck,
    )
    event = make_event("runtime.remote")

    await pipe.put(event, "mailtruck", recipient="node-two")

    mailtruck.put.assert_awaited_once_with(event, recipient="node-two")
    assert APIX_EVENT_REGISTRY.get_registered_events() == frozenset(
        {"runtime.remote"}
    )


@pytest.mark.asyncio
async def test_failed_publish_does_not_record_event_name():
    mailtruck = AsyncMock()
    mailtruck.put.side_effect = RuntimeError("publish failed")
    pipe = ApixEventPipe(
        remote_enabled=False,
        mailtruck=mailtruck,
    )

    with pytest.raises(RuntimeError, match="publish failed"):
        await pipe.put(
            make_event("runtime.failed"),
            "mailtruck",
            recipient="node-two",
        )

    assert APIX_EVENT_REGISTRY.get_registered_events() == frozenset()
