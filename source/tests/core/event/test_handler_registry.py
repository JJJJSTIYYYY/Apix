"""Tests for the versioned, glob-aware event handler registry."""

import time
from concurrent.futures import Future
from unittest.mock import AsyncMock, Mock
from unittest.mock import patch

import pytest

import apix.core.event.handler_registry as handler_registry_module
from apix.core.event.base import ApixEvent, ApixEventHandler, EventType
from apix.core.event.event_registry import apix_event_registry
from apix.core.event.event_loop import ApixEventLoop
from apix.core.event.event_pipe import ApixEventPipe
from apix.core.event.handler_registry import (
    ApixHandlerRegistry,
    apix_handler_registry,
    delete_handler_from_registry,
    get_unmatched_subscriptions,
    subscribe,
    unsubscribe,
)
from apix.core.utils.exception import (
    EventHandlerAlreadyRegisteredError,
    EventHandlerNotRegisteredError,
)


@pytest.fixture(autouse=True)
def reset_global_handler_registry():
    """Isolate the process-global singleton for every registry test."""
    apix_handler_registry.shutdown_prewarmer(
        wait=True,
        cancel_futures=True,
    )
    apix_handler_registry._prewarm_jobs.clear()
    apix_handler_registry.registry.clear()
    apix_handler_registry.priority_buckets.clear()
    apix_handler_registry.cached_chain.clear()
    apix_handler_registry._register_order = 0
    yield
    apix_handler_registry.shutdown_prewarmer(
        wait=True,
        cancel_futures=True,
    )
    apix_handler_registry._prewarm_jobs.clear()
    apix_handler_registry.registry.clear()
    apix_handler_registry.priority_buckets.clear()
    apix_handler_registry.cached_chain.clear()
    apix_handler_registry._register_order = 0


def make_entry(
    name: str,
    *,
    subscribe_patterns: list[str] | None = None,
    filter_event: list[str] | None = None,
    priority: float | None = 1,
    between_handlers: tuple[str | None, str | None] | None = None,
    callback=None,
) -> ApixEventHandler:
    """Create one valid handler registry entry."""
    return ApixEventHandler(
        name=name,
        register_order=0,
        callback=AsyncMock() if callback is None else callback,
        subscribe=["event.*"] if subscribe_patterns is None else subscribe_patterns,
        filter_event=[] if filter_event is None else filter_event,
        priority=priority,
        between_handlers=between_handlers,
    )


def observe_events(*event_names: str) -> None:
    """Record exact event names without publishing queue items."""
    for event_name in event_names:
        apix_event_registry.record_event(
            ApixEvent(
                event_id=f"event-{event_name}",
                event_type=EventType.WORKFLOW,
                event_name=event_name,
                context=None,
                timestamp=time.time(),
            )
        )


def test_registry_is_singleton():
    assert ApixHandlerRegistry() is apix_handler_registry


def test_pattern_normalisation_accepts_one_string():
    assert ApixHandlerRegistry._normalise_patterns(
        "event.one",
        argument_name="events",
    ) == ["event.one"]


def test_empty_chain_is_cached_for_exact_event_name():
    chain = apix_handler_registry.get_handlers_chain_for_event("event.one")

    assert chain == []
    assert apix_handler_registry.cached_chain == {"event.one": [[]]}
    assert apix_handler_registry.get_current_version_for_event("event.one") == 0


def test_glob_matching_is_case_sensitive_and_filters_are_exclusions():
    apix_handler_registry.register_handler(
        make_entry(
            "handler",
            subscribe_patterns=["Build.[A-C]*"],
            filter_event=["Build.Bad*"],
        )
    )

    assert apix_handler_registry.get_handlers_chain_for_event("Build.App") == [
        "handler"
    ]
    assert apix_handler_registry.get_handlers_chain_for_event("Build.BadJob") == []
    assert apix_handler_registry.get_handlers_chain_for_event("build.App") == []
    assert set(apix_handler_registry.cached_chain) == {
        "Build.App",
        "Build.BadJob",
        "build.App",
    }


def test_unmatched_subscription_query_respects_filters_and_case():
    observe_events("event.one", "event.skip", "Event.Case")
    apix_handler_registry.register_handler(
        make_entry(
            "handler",
            subscribe_patterns=["event.*", "other.*", "Event.*", "EVENT.*"],
            filter_event=["event.skip"],
        )
    )

    assert apix_handler_registry.get_unmatched_subscriptions("handler") == [
        "other.*",
        "EVENT.*",
    ]
    assert get_unmatched_subscriptions("handler") == [
        "other.*",
        "EVENT.*",
    ]

    with pytest.raises(EventHandlerNotRegisteredError):
        get_unmatched_subscriptions("missing")


def test_small_wildcard_registration_prewarms_known_matching_events():
    observe_events("known.one", "known.skip", "other.one")
    apix_handler_registry.register_handler(
        make_entry(
            "exact",
            subscribe_patterns=["known.one"],
            priority=10,
        )
    )
    assert apix_handler_registry.cached_chain == {}

    apix_handler_registry.register_handler(
        make_entry(
            "wildcard",
            subscribe_patterns=["known.*"],
            filter_event=["known.skip"],
            priority=1,
        )
    )

    assert apix_handler_registry.cached_chain == {
        "known.one": [["exact", "wildcard"]]
    }


def test_process_safe_resolver_applies_subscriptions_and_filters():
    patterns = (
        ("selected", ("known.*",), ()),
        ("unsubscribed", ("other.*",), ()),
        ("filtered", ("known.*",), ("known.one",)),
    )

    assert handler_registry_module._resolve_handler_chains(
        ("known.one",),
        patterns,
    ) == {"known.one": ["selected"]}


def test_pattern_snapshot_skips_stale_bucket_names():
    apix_handler_registry.register_handler(make_entry("stale"))
    del apix_handler_registry.registry["stale"]

    assert apix_handler_registry._handler_pattern_snapshot() == ()


@pytest.mark.asyncio
async def test_large_wildcard_prewarm_uses_process_pool(monkeypatch):
    monkeypatch.setattr(
        handler_registry_module,
        "_PREWARM_PROCESS_THRESHOLD",
        1,
    )
    monkeypatch.setattr(
        handler_registry_module,
        "_PREWARM_MAX_WORKERS",
        2,
    )
    observe_events(*(f"parallel.{index}" for index in range(6)))

    apix_handler_registry.register_handler(
        make_entry(
            "parallel_handler",
            subscribe_patterns=["parallel.*"],
        )
    )

    assert apix_handler_registry._prewarm_executor is not None
    assert apix_handler_registry.wait_for_prewarm(timeout=10) is True
    assert {
        event_name: versions[-1]
        for event_name, versions in apix_handler_registry.cached_chain.items()
    } == {
        f"parallel.{index}": ["parallel_handler"]
        for index in range(6)
    }


def test_stale_process_result_cannot_overwrite_newer_cache_version():
    apix_handler_registry.cached_chain["event.one"] = [None]
    future = Future()
    apix_handler_registry._prewarm_jobs[future] = {"event.one": 0}
    future.set_result({"event.one": ["stale_handler"]})
    apix_handler_registry.cached_chain["event.one"].append(None)

    apix_handler_registry._complete_prewarm_job(future)

    assert apix_handler_registry.cached_chain["event.one"] == [None, None]


def test_wait_for_prewarm_reports_timeout_and_handles_cancelled_job():
    future = Future()
    apix_handler_registry._prewarm_jobs[future] = {}

    assert apix_handler_registry.wait_for_prewarm(timeout=0) is False
    future.cancel()
    apix_handler_registry._complete_prewarm_job(future)
    assert apix_handler_registry.wait_for_prewarm(timeout=0) is True


def test_prewarm_job_failure_is_logged_without_cache_mutation():
    future = Future()
    apix_handler_registry._prewarm_jobs[future] = {"event.one": 0}
    future.set_exception(RuntimeError("worker failed"))

    with patch("apix.core.event.handler_registry.logger") as logger:
        apix_handler_registry._complete_prewarm_job(future)

        logger.error.assert_called_once()
    assert apix_handler_registry.cached_chain == {}


def test_shutdown_prewarmer_merges_completed_jobs():
    executor = Mock()
    future = Future()
    future.set_result({"event.one": ["handler"]})
    apix_handler_registry.cached_chain["event.one"] = [None]
    apix_handler_registry._prewarm_executor = executor
    apix_handler_registry._prewarm_jobs[future] = {"event.one": 0}

    apix_handler_registry.shutdown_prewarmer(
        wait=False,
        cancel_futures=True,
    )

    executor.shutdown.assert_called_once_with(
        wait=False,
        cancel_futures=True,
    )
    assert apix_handler_registry.cached_chain["event.one"] == [["handler"]]
    assert apix_handler_registry._prewarm_jobs == {}


def test_priority_buckets_dispatch_higher_first_and_preserve_registration_order():
    for entry in (
        make_entry("low", priority=1),
        make_entry("high_first", priority=10),
        make_entry("high_second", priority=10),
    ):
        apix_handler_registry.register_handler(entry)

    assert apix_handler_registry.priority_buckets == {
        1: ["low"],
        10: ["high_first", "high_second"],
    }
    assert apix_handler_registry.get_handlers_chain_for_event("event.one") == [
        "high_first",
        "high_second",
        "low",
    ]


@pytest.mark.parametrize(
    ("between_handlers", "expected"),
    [
        (("left", None), ["left", "middle", "right"]),
        ((None, "right"), ["left", "middle", "right"]),
        (("left", "right"), ["left", "middle", "right"]),
    ],
)
def test_between_handlers_inserts_at_requested_boundary(
    between_handlers,
    expected,
):
    apix_handler_registry.register_handler(make_entry("left", priority=5))
    apix_handler_registry.register_handler(make_entry("right", priority=5))
    apix_handler_registry.register_handler(
        make_entry(
            "middle",
            priority=None,
            between_handlers=between_handlers,
        )
    )

    assert apix_handler_registry.priority_buckets[5] == expected


def test_right_boundary_controls_cross_priority_insertion():
    apix_handler_registry.register_handler(make_entry("left", priority=10))
    apix_handler_registry.register_handler(make_entry("right", priority=1))
    apix_handler_registry.register_handler(
        make_entry(
            "middle",
            priority=None,
            between_handlers=("left", "right"),
        )
    )

    assert apix_handler_registry.priority_buckets[1] == ["middle", "right"]
    assert apix_handler_registry.get_handlers_chain_for_event("event.one") == [
        "left",
        "middle",
        "right",
    ]


def test_between_handlers_rejects_missing_or_reversed_boundaries():
    apix_handler_registry.register_handler(make_entry("left", priority=1))
    apix_handler_registry.register_handler(make_entry("right", priority=10))

    with pytest.raises(EventHandlerNotRegisteredError, match="missing"):
        apix_handler_registry.register_handler(
            make_entry(
                "unknown_left",
                priority=None,
                between_handlers=("missing", "right"),
            )
        )
    with pytest.raises(EventHandlerNotRegisteredError, match="missing"):
        apix_handler_registry.register_handler(
            make_entry(
                "unknown_right",
                priority=None,
                between_handlers=("left", "missing"),
            )
        )
    with pytest.raises(ValueError, match="must be before"):
        apix_handler_registry.register_handler(
            make_entry(
                "reversed",
                priority=None,
                between_handlers=("left", "right"),
            )
        )


def test_between_handlers_rejects_reversed_names_in_same_bucket():
    apix_handler_registry.register_handler(make_entry("first", priority=1))
    apix_handler_registry.register_handler(make_entry("second", priority=1))

    with pytest.raises(ValueError, match="must be before"):
        apix_handler_registry.register_handler(
            make_entry(
                "middle",
                priority=None,
                between_handlers=("second", "first"),
            )
        )


def test_register_invalidates_only_matching_exact_event_caches():
    assert apix_handler_registry.get_handlers_chain_for_event("event.one") == []
    assert apix_handler_registry.get_handlers_chain_for_event("other.one") == []

    apix_handler_registry.register_handler(
        make_entry(
            "handler",
            subscribe_patterns=["event.*"],
            filter_event=["event.skip"],
        )
    )

    assert apix_handler_registry.cached_chain["event.one"] == [[], None]
    assert apix_handler_registry.cached_chain["other.one"] == [[]]
    assert apix_handler_registry.get_handlers_chain_for_event("event.one") == [
        "handler"
    ]
    assert apix_handler_registry.get_handlers_chain_for_event(
        "event.one", version=0
    ) == []


def test_register_rejects_invalid_entries_without_partial_mutation():
    with pytest.raises(TypeError, match="ApixEventHandler"):
        apix_handler_registry.register_handler(object())
    with pytest.raises(ValueError, match="name"):
        apix_handler_registry.register_handler(make_entry(""))
    with pytest.raises(TypeError, match="callback"):
        apix_handler_registry.register_handler(
            make_entry("no_callback", callback=False)
        )
    with pytest.raises(ValueError, match="subscribe"):
        apix_handler_registry.register_handler(
            make_entry("no_subscriptions", subscribe_patterns=[])
        )
    with pytest.raises(TypeError, match="priority"):
        apix_handler_registry.register_handler(
            make_entry("no_priority", priority=None)
        )

    assert apix_handler_registry.registry == {}
    assert apix_handler_registry.priority_buckets == {}


def test_register_rejects_duplicate_name_and_priority_with_between():
    entry = make_entry("handler")
    apix_handler_registry.register_handler(entry)

    with pytest.raises(EventHandlerAlreadyRegisteredError):
        apix_handler_registry.register_handler(make_entry("handler"))
    with pytest.raises(ValueError, match="cannot be set together"):
        apix_handler_registry.register_handler(
            make_entry(
                "invalid_between",
                priority=1,
                between_handlers=("handler", None),
            )
        )


@pytest.mark.parametrize(
    "between_handlers",
    [
        (None, None),
        ("same", "same"),
        ("left",),
        ("", None),
    ],
)
def test_direct_registration_rejects_invalid_between_handlers(
    between_handlers,
):
    with pytest.raises(ValueError):
        apix_handler_registry.register_handler(
            make_entry(
                "invalid",
                priority=None,
                between_handlers=between_handlers,
            )
        )


def test_direct_registration_rejects_non_finite_priority():
    with pytest.raises(ValueError, match="finite"):
        apix_handler_registry.register_handler(
            make_entry("invalid", priority=float("nan"))
        )


def test_get_chain_validates_name_and_version():
    with pytest.raises(ValueError, match="event_name"):
        apix_handler_registry.get_handlers_chain_for_event("")
    with pytest.raises(ValueError, match="does not exist"):
        apix_handler_registry.get_handlers_chain_for_event("event.one", -1)
    with pytest.raises(ValueError, match="does not exist"):
        apix_handler_registry.get_handlers_chain_for_event("event.one", True)
    with pytest.raises(ValueError, match="does not exist"):
        apix_handler_registry.get_handlers_chain_for_event("event.one", 2)


def test_unregister_retains_registry_entry_and_old_cache_version():
    entry = make_entry("handler")
    apix_handler_registry.register_handler(entry)
    assert apix_handler_registry.get_handlers_chain_for_event("event.one") == [
        "handler"
    ]

    apix_handler_registry.unregister_handler("handler")

    assert apix_handler_registry.get_handler("handler") is entry
    assert apix_handler_registry.priority_buckets == {}
    assert apix_handler_registry.cached_chain["event.one"] == [
        ["handler"],
        None,
    ]
    assert apix_handler_registry.get_handlers_chain_for_event(
        "event.one", version=0
    ) == ["handler"]
    assert apix_handler_registry.get_handlers_chain_for_event("event.one") == []

    # Repeated unregistration is idempotent and does not create a new version.
    apix_handler_registry.unregister_handler("handler")
    assert len(apix_handler_registry.cached_chain["event.one"]) == 2


def test_partial_unregister_adds_filters_and_invalidates_selected_events_only():
    entry = make_entry("handler")
    apix_handler_registry.register_handler(entry)
    apix_handler_registry.get_handlers_chain_for_event("event.one")
    apix_handler_registry.get_handlers_chain_for_event("event.two")

    apix_handler_registry.unregister_handler("handler", ["event.one"])

    assert entry.filter_event == ["event.one"]
    assert apix_handler_registry.cached_chain["event.one"][-1] is None
    assert len(apix_handler_registry.cached_chain["event.two"]) == 1
    assert apix_handler_registry.get_handlers_chain_for_event("event.one") == []
    assert apix_handler_registry.get_handlers_chain_for_event("event.two") == [
        "handler"
    ]

    version_count = len(apix_handler_registry.cached_chain["event.one"])
    apix_handler_registry.unregister_handler("handler", ["event.one"])
    assert len(apix_handler_registry.cached_chain["event.one"]) == version_count


def test_unregister_unknown_handler_raises():
    with pytest.raises(EventHandlerNotRegisteredError):
        apix_handler_registry.unregister_handler("missing")


def test_delete_active_handler_invalidates_cache_and_removes_entry():
    apix_handler_registry.register_handler(make_entry("handler"))
    apix_handler_registry.get_handlers_chain_for_event("event.one")

    apix_handler_registry.delete_handler_from_registry(
        "handler",
        event_names=["event.one"],
    )

    assert apix_handler_registry.get_handler("handler") is None
    assert apix_handler_registry.priority_buckets == {}
    assert apix_handler_registry.cached_chain["event.one"][-1] is None


def test_delete_already_unregistered_handler_does_not_add_version():
    apix_handler_registry.register_handler(make_entry("handler"))
    apix_handler_registry.get_handlers_chain_for_event("event.one")
    apix_handler_registry.unregister_handler("handler")
    version_count = len(apix_handler_registry.cached_chain["event.one"])

    apix_handler_registry.delete_handler_from_registry("handler")

    assert len(apix_handler_registry.cached_chain["event.one"]) == version_count
    with pytest.raises(EventHandlerNotRegisteredError):
        apix_handler_registry.delete_handler_from_registry("handler")


def test_global_subscribe_builds_full_handler_metadata():
    @subscribe(
        "event.*",
        "event.*",
        filter_event=["event.skip"],
        priority=2.5,
        stop_when_error=False,
        time_out=0,
        background=True,
    )
    async def handler(event):
        return None

    entry = apix_handler_registry.get_handler("handler")
    assert entry is not None
    assert entry.subscribe == ["event.*"]
    assert entry.filter_event == ["event.skip"]
    assert entry.priority == 2.5
    assert entry.stop_when_error is False
    assert entry.time_out is None
    assert entry.background is True
    assert entry.register_order == 0
    assert apix_handler_registry._register_order == 1


def test_global_subscribe_defaults_priority_and_preserves_decorated_function():
    async def handler(event):
        return None

    decorated = subscribe("event.one")(handler)

    assert decorated is handler
    assert apix_handler_registry.get_handler("handler").priority == 1


def test_global_subscribe_deduplicates_by_handler_name():
    @subscribe("event.one")
    async def handler(event):
        return None

    async def replacement(event):
        return None

    replacement.__name__ = "handler"
    assert subscribe("event.two")(replacement) is replacement
    assert apix_handler_registry.get_handler("handler").callback is handler

    with pytest.raises(EventHandlerAlreadyRegisteredError):
        subscribe("event.two", exist_ok=False)(replacement)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"between_handlers": (None, None)},
        {"between_handlers": ("same", "same")},
        {"between_handlers": ("left",)},
        {"between_handlers": ["left", "right"]},
        {"between_handlers": ("left", None), "priority": 1},
    ],
)
def test_global_subscribe_rejects_invalid_between_handlers(kwargs):
    with pytest.raises(ValueError):
        subscribe("event.one", **kwargs)


def test_global_subscribe_rejects_empty_boundary_name():
    with pytest.raises(ValueError, match="Boundary"):
        subscribe("event.one", between_handlers=("", None))


@pytest.mark.parametrize("event_names", [(), ("",), (None,)])
def test_global_subscribe_rejects_invalid_event_names(event_names):
    with pytest.raises(ValueError):
        subscribe(*event_names)


def test_global_unsubscribe_and_delete_wrappers_support_missing_ok():
    unsubscribe("missing")
    delete_handler_from_registry("missing")

    with pytest.raises(EventHandlerNotRegisteredError):
        unsubscribe("missing", missing_ok=False)
    with pytest.raises(EventHandlerNotRegisteredError):
        delete_handler_from_registry("missing", missing_ok=False)


def test_global_unsubscribe_retains_entry_and_delete_removes_it():
    @subscribe("event.one")
    async def handler(event):
        return None

    unsubscribe("handler")
    assert apix_handler_registry.get_handler("handler") is not None

    delete_handler_from_registry("handler")
    assert apix_handler_registry.get_handler("handler") is None


@pytest.mark.asyncio
async def test_event_publish_freezes_chain_before_later_registration():
    calls = []

    @subscribe("versioned.*", priority=1)
    async def original_handler(event):
        calls.append("original")

    pipe = ApixEventPipe(remote_enabled=False)
    await pipe.post_event(
        event_type=EventType.WORKFLOW,
        event_name="versioned.event",
    )
    queued_event = await pipe.get()
    assert queued_event._handler_chain_version == 0
    assert apix_handler_registry.cached_chain["versioned.event"] == [
        ["original_handler"]
    ]

    @subscribe("versioned.*", priority=2)
    async def later_handler(event):
        calls.append("later")

    event_loop = ApixEventLoop(apix_handler_registry)
    await event_loop._dispatch_semaphore.acquire()
    await event_loop._dispatch_event(queued_event)
    pipe.task_done()
    assert calls == ["original"]

    await pipe.post_event(
        event_type=EventType.WORKFLOW,
        event_name="versioned.event",
    )
    current_event = await pipe.get()
    assert current_event._handler_chain_version == 1
    await event_loop._dispatch_semaphore.acquire()
    await event_loop._dispatch_event(current_event)
    pipe.task_done()
    assert calls == ["original", "later", "original"]


def test_builtin_put_nowait_binds_current_chain_version():
    apix_handler_registry.register_handler(make_entry("handler"))
    pipe = ApixEventPipe(remote_enabled=False)
    event = ApixEvent(
        event_id="event-id",
        event_type=EventType.WORKFLOW,
        event_name="event.one",
        context=None,
        timestamp=time.time(),
    )

    pipe.put_nowait(event)

    assert event._handler_chain_version == 0
    assert pipe.get_nowait() is event
    pipe.task_done()


@pytest.mark.asyncio
async def test_dispatch_skips_name_missing_from_registry():
    apix_handler_registry.register_handler(make_entry("handler"))
    apix_handler_registry.get_handlers_chain_for_event("event.one")
    apix_handler_registry.delete_handler_from_registry("handler")
    event = ApixEvent(
        event_id="event-id",
        event_type=EventType.WORKFLOW,
        event_name="event.one",
        context=None,
        timestamp=time.time(),
        _handler_chain_version=0,
    )
    event_loop = ApixEventLoop(apix_handler_registry)

    await event_loop._dispatch_semaphore.acquire()
    with patch("apix.core.event.event_loop.logger") as logger:
        result = await event_loop._dispatch_event(event)

    assert result is event
    assert event.accepted is True
    logger.warning.assert_called_once()
