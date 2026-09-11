"""Tests for the current, glob-aware event handler registry."""

import time
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from apix.core.event.base import ApixEvent, ApixEventHandler, EventType
from apix.core.event.event_registry import APIX_EVENT_REGISTRY
from apix.core.event.event_loop import ApixEventLoop
from apix.core.event.event_pipe import ApixEventPipe
from apix.core.event.handler_registry import (
    ApixHandlerRegistry,
    APIX_HANDLER_REGISTRY,
    unsubscribe,
    get_unmatched_subscriptions,
    subscribe,
)
from apix.core.utils.exception import (
    EventHandlerAlreadyRegisteredError,
    EventHandlerNotRegisteredError,
)


@pytest.fixture(autouse=True)
def reset_global_handler_registry():
    """Isolate the process-global singleton for every registry test."""
    APIX_HANDLER_REGISTRY.registry.clear()
    APIX_HANDLER_REGISTRY.priority_buckets.clear()
    APIX_HANDLER_REGISTRY.cached_chain.clear()
    APIX_HANDLER_REGISTRY._register_order = 0
    yield
    APIX_HANDLER_REGISTRY.registry.clear()
    APIX_HANDLER_REGISTRY.priority_buckets.clear()
    APIX_HANDLER_REGISTRY.cached_chain.clear()
    APIX_HANDLER_REGISTRY._register_order = 0


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
    entry = ApixEventHandler(AsyncMock() if callback is None else callback)
    entry.name = name
    entry._register_order = 0
    entry.subscribe = ["event.*"] if subscribe_patterns is None else subscribe_patterns
    entry.filter_event = [] if filter_event is None else filter_event
    entry.priority = priority
    entry.between_handlers = between_handlers
    return entry



def observe_events(*event_names: str) -> None:
    """Record exact event names without publishing queue items."""
    for event_name in event_names:
        APIX_EVENT_REGISTRY.record_event(
            ApixEvent(
                event_id=f"event-{event_name}",
                event_type=EventType.WORKFLOW,
                event_name=event_name,
                context=None,
                timestamp=time.time(),
            )
        )


def test_registry_is_singleton():
    assert ApixHandlerRegistry() is APIX_HANDLER_REGISTRY


def test_pattern_normalisation_accepts_one_string():
    assert ApixHandlerRegistry._normalise_patterns(
        "event.one",
        argument_name="events",
    ) == ["event.one"]


def test_empty_chain_is_cached_for_exact_event_name():
    chain = APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one")

    assert chain == []
    assert APIX_HANDLER_REGISTRY.cached_chain == {"event.one": []}
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one") is chain


def test_glob_matching_is_case_sensitive_and_filters_are_exclusions():
    APIX_HANDLER_REGISTRY.register_handler(
        make_entry(
            "handler",
            subscribe_patterns=["Build.[A-C]*"],
            filter_event=["Build.Bad*"],
        )
    )

    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("Build.App") == [
        "handler"
    ]
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("Build.BadJob") == []
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("build.App") == []
    assert set(APIX_HANDLER_REGISTRY.cached_chain) == {
        "Build.App",
        "Build.BadJob",
        "build.App",
    }


def test_unmatched_subscription_query_respects_filters_and_case():
    observe_events("event.one", "event.skip", "Event.Case")
    APIX_HANDLER_REGISTRY.register_handler(
        make_entry(
            "handler",
            subscribe_patterns=["event.*", "other.*", "Event.*", "EVENT.*"],
            filter_event=["event.skip"],
        )
    )

    assert APIX_HANDLER_REGISTRY.get_unmatched_subscriptions("handler") == [
        "other.*",
        "EVENT.*",
    ]
    assert get_unmatched_subscriptions("handler") == [
        "other.*",
        "EVENT.*",
    ]

    with pytest.raises(EventHandlerNotRegisteredError):
        get_unmatched_subscriptions("missing")


def test_wildcard_registration_leaves_observed_event_chains_lazy():
    observe_events("known.one", "known.skip", "other.one")
    APIX_HANDLER_REGISTRY.register_handler(
        make_entry(
            "exact",
            subscribe_patterns=["known.one"],
            priority=10,
        )
    )
    assert APIX_HANDLER_REGISTRY.cached_chain == {}

    APIX_HANDLER_REGISTRY.register_handler(
        make_entry(
            "wildcard",
            subscribe_patterns=["known.*"],
            filter_event=["known.skip"],
            priority=1,
        )
    )

    assert APIX_HANDLER_REGISTRY.cached_chain == {}
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("known.one") == [
        "exact",
        "wildcard",
    ]
    assert APIX_HANDLER_REGISTRY.cached_chain == {
        "known.one": ["exact", "wildcard"]
    }


def test_priority_buckets_dispatch_higher_first_and_preserve_registration_order():
    for entry in (
        make_entry("low", priority=1),
        make_entry("high_first", priority=10),
        make_entry("high_second", priority=10),
    ):
        APIX_HANDLER_REGISTRY.register_handler(entry)

    assert APIX_HANDLER_REGISTRY.priority_buckets == {
        1: ["low"],
        10: ["high_first", "high_second"],
    }
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one") == [
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
    APIX_HANDLER_REGISTRY.register_handler(make_entry("left", priority=5))
    APIX_HANDLER_REGISTRY.register_handler(make_entry("right", priority=5))
    APIX_HANDLER_REGISTRY.register_handler(
        make_entry(
            "middle",
            priority=None,
            between_handlers=between_handlers,
        )
    )

    assert APIX_HANDLER_REGISTRY.priority_buckets[5] == expected


def test_right_boundary_controls_cross_priority_insertion():
    APIX_HANDLER_REGISTRY.register_handler(make_entry("left", priority=10))
    APIX_HANDLER_REGISTRY.register_handler(make_entry("right", priority=1))
    APIX_HANDLER_REGISTRY.register_handler(
        make_entry(
            "middle",
            priority=None,
            between_handlers=("left", "right"),
        )
    )

    assert APIX_HANDLER_REGISTRY.priority_buckets[1] == ["middle", "right"]
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one") == [
        "left",
        "middle",
        "right",
    ]


def test_between_handlers_rejects_missing_or_reversed_boundaries():
    APIX_HANDLER_REGISTRY.register_handler(make_entry("left", priority=1))
    APIX_HANDLER_REGISTRY.register_handler(make_entry("right", priority=10))

    with pytest.raises(EventHandlerNotRegisteredError, match="missing"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry(
                "unknown_left",
                priority=None,
                between_handlers=("missing", "right"),
            )
        )
    with pytest.raises(EventHandlerNotRegisteredError, match="missing"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry(
                "unknown_right",
                priority=None,
                between_handlers=("left", "missing"),
            )
        )
    with pytest.raises(ValueError, match="must be before"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry(
                "reversed",
                priority=None,
                between_handlers=("left", "right"),
            )
        )


def test_between_handlers_rejects_reversed_names_in_same_bucket():
    APIX_HANDLER_REGISTRY.register_handler(make_entry("first", priority=1))
    APIX_HANDLER_REGISTRY.register_handler(make_entry("second", priority=1))

    with pytest.raises(ValueError, match="must be before"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry(
                "middle",
                priority=None,
                between_handlers=("second", "first"),
            )
        )


def test_register_invalidates_only_matching_exact_event_caches():
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one") == []
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("other.one") == []

    APIX_HANDLER_REGISTRY.register_handler(
        make_entry(
            "handler",
            subscribe_patterns=["event.*"],
            filter_event=["event.skip"],
        )
    )

    assert APIX_HANDLER_REGISTRY.cached_chain["event.one"] is None
    assert APIX_HANDLER_REGISTRY.cached_chain["other.one"] == []
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one") == [
        "handler"
    ]


def test_register_rejects_invalid_entries_without_partial_mutation():
    with pytest.raises(TypeError, match="ApixEventHandler"):
        APIX_HANDLER_REGISTRY.register_handler(object())
    with pytest.raises(ValueError, match="name"):
        APIX_HANDLER_REGISTRY.register_handler(make_entry(""))
    with pytest.raises(TypeError, match="callable"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry("no_callback", callback=False)
        )
    with pytest.raises(ValueError, match="subscribe"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry("no_subscriptions", subscribe_patterns=[])
        )
    with pytest.raises(TypeError, match="priority"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry("no_priority", priority=None)
        )

    assert APIX_HANDLER_REGISTRY.registry == {}
    assert APIX_HANDLER_REGISTRY.priority_buckets == {}


def test_register_rejects_duplicate_name_and_priority_with_between():
    entry = make_entry("handler")
    APIX_HANDLER_REGISTRY.register_handler(entry)

    with pytest.raises(EventHandlerAlreadyRegisteredError):
        APIX_HANDLER_REGISTRY.register_handler(make_entry("handler"))
    with pytest.raises(ValueError, match="cannot be set together"):
        APIX_HANDLER_REGISTRY.register_handler(
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
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry(
                "invalid",
                priority=None,
                between_handlers=between_handlers,
            )
        )


def test_direct_registration_rejects_non_finite_priority():
    with pytest.raises(ValueError, match="finite"):
        APIX_HANDLER_REGISTRY.register_handler(
            make_entry("invalid", priority=float("nan"))
        )


@pytest.mark.parametrize("name", ["", None, 1])
def test_get_chain_validates_name(name):
    with pytest.raises(ValueError, match="event_name"):
        APIX_HANDLER_REGISTRY.get_handlers_chain_for_event(name)


def test_unregister_removes_entry_and_preserves_already_resolved_list():
    APIX_HANDLER_REGISTRY.register_handler(make_entry("handler"))
    chain = APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one")
    APIX_HANDLER_REGISTRY.unregister_handler("handler")
    assert APIX_HANDLER_REGISTRY.get_handler("handler") is None
    assert APIX_HANDLER_REGISTRY.priority_buckets == {}
    assert APIX_HANDLER_REGISTRY.cached_chain["event.one"] is None
    assert chain == ["handler"]
    assert APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one") == []


def test_unregister_unknown_handler_raises():
    with pytest.raises(EventHandlerNotRegisteredError):
        APIX_HANDLER_REGISTRY.unregister_handler("missing")


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

    entry = APIX_HANDLER_REGISTRY.get_handler("handler")
    assert entry is not None
    assert entry.subscribe == ["event.*"]
    assert entry.filter_event == ["event.skip"]
    assert entry.priority == 2.5
    assert entry.stop_when_error is False
    assert entry.time_out is None
    assert entry.background is True
    assert entry._register_order == 0
    assert APIX_HANDLER_REGISTRY._register_order == 1


def test_global_subscribe_defaults_priority_and_preserves_decorated_function():
    async def handler(event):
        return None

    decorated = subscribe("event.one")(handler)

    assert decorated is handler
    assert APIX_HANDLER_REGISTRY.get_handler("handler").priority == 1


def test_global_subscribe_replaces_by_handler_name():
    @subscribe("event.one")
    async def handler(event):
        return None

    async def replacement(event):
        return None

    replacement.__name__ = "handler"
    assert subscribe("event.two")(replacement) is replacement
    assert APIX_HANDLER_REGISTRY.get_handler("handler").core_func is replacement

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
        subscribe("event.one", **kwargs)(make_entry("handler"))


def test_global_subscribe_rejects_empty_boundary_name():
    with pytest.raises(ValueError, match="Boundary"):
        subscribe("event.one", between_handlers=("", None))(make_entry("handler"))


@pytest.mark.parametrize("event_names", [(), ("",), (None,)])
def test_global_subscribe_rejects_invalid_event_names(event_names):
    with pytest.raises(ValueError):
        subscribe(*event_names)(make_entry("handler"))


def test_global_unsubscribe_supports_missing_ok():
    unsubscribe("missing")
    with pytest.raises(EventHandlerNotRegisteredError):
        unsubscribe("missing", missing_ok=False)


def test_global_unsubscribe_removes_entry():
    @subscribe("event.one")
    async def handler(event):
        return None

    unsubscribe("handler")
    assert APIX_HANDLER_REGISTRY.get_handler("handler") is None
    unsubscribe("handler")


def test_builtin_put_nowait_does_not_resolve_chain():
    APIX_HANDLER_REGISTRY.register_handler(make_entry("handler"))
    pipe = ApixEventPipe(remote_enabled=False)
    event = ApixEvent("event-id", EventType.WORKFLOW, "event.one", None, 0)
    with patch.object(APIX_HANDLER_REGISTRY, "get_handlers_chain_for_event") as resolve:
        pipe.put_nowait(event)
        resolve.assert_not_called()
    assert APIX_HANDLER_REGISTRY.cached_chain == {}
    assert pipe.get_nowait() is event
    pipe.task_done()


@pytest.mark.asyncio
async def test_dispatch_skips_name_missing_from_registry():
    APIX_HANDLER_REGISTRY.register_handler(make_entry("handler"))
    chain = APIX_HANDLER_REGISTRY.get_handlers_chain_for_event("event.one")
    unsubscribe("handler")
    event = ApixEvent("event-id", EventType.WORKFLOW, "event.one", None, 0)
    event_loop = ApixEventLoop(APIX_HANDLER_REGISTRY)
    with patch("apix.core.event.event_loop.logger") as logger:
        result = await event_loop._dispatch_event(
            event,
            chain,
        )
    assert result is event
    assert not event.has_error
    logger.warning.assert_not_called()
    logger.error.assert_not_called()


@pytest.mark.parametrize("initial", ["missing", "expired", "empty", "populated"])
def test_four_cache_states_rebuild_only_when_required(initial):
    registry = APIX_HANDLER_REGISTRY
    if initial != "missing":
        registry.cached_chain["event.one"] = {
            "expired": None, "empty": [], "populated": ["cached"],
        }[initial]
    saved = registry.cached_chain.get("event.one")
    with patch.object(registry, "_iter_active_handler_names", return_value=iter(())) as build:
        chain = registry.get_handlers_chain_for_event("event.one")
        if initial in ("missing", "expired"):
            build.assert_called_once()
            assert chain == []
        else:
            build.assert_not_called()
            assert chain is saved
        assert registry.cached_chain["event.one"] is chain


def test_replacement_invalidates_union_of_old_and_new_matches_with_filters():
    registry = APIX_HANDLER_REGISTRY
    old = make_entry("handler", subscribe_patterns=["old.*", "shared.*"],
                     filter_event=["shared.new", "shared.neither"])
    registry.register_handler(old)
    names = ["old.one", "new.one", "shared.old", "shared.new", "shared.neither", "unrelated"]
    saved = {name: registry.get_handlers_chain_for_event(name) for name in names}
    new = make_entry("handler", subscribe_patterns=["new.*", "shared.*"],
                     filter_event=["shared.old", "shared.neither"], priority=10)
    registry.register_handler(new, exist_ok=True)
    assert registry.get_handler("handler") is new
    assert registry.priority_buckets == {10: ["handler"]}
    for name in names[:4]:
        assert registry.cached_chain[name] is None
    for name in names[4:]:
        assert registry.cached_chain[name] is saved[name]
    assert saved["old.one"] == ["handler"]
    assert registry.get_handlers_chain_for_event("old.one") == []
    assert registry.get_handlers_chain_for_event("new.one") == ["handler"]


@pytest.mark.parametrize("options", [
    {"priority": float("nan")},
    {"priority": "bad"},
    {"between_handlers": (None, "missing")},
    {"between_handlers": (None, "handler")},
    {"filter_event": [""]},
    {"exist_ok": False},
])
def test_failed_instance_replacement_preserves_registration_and_cache(options):
    registry = APIX_HANDLER_REGISTRY
    async def core(event):
        pass
    entry = ApixEventHandler(core, on_error=AsyncMock(), background=True)
    entry.name = "handler"
    subscribe("event.*", priority=5)(entry)
    old_metadata = entry.__dict__.copy()
    chain = registry.get_handlers_chain_for_event("event.one")
    with pytest.raises((ValueError, TypeError, EventHandlerNotRegisteredError,
                        EventHandlerAlreadyRegisteredError)):
        subscribe("other.*", background=False, **options)(entry)
    assert registry.get_handler("handler") is entry
    assert entry.__dict__ == old_metadata
    assert registry.priority_buckets == {5: ["handler"]}
    assert registry.cached_chain["event.one"] is chain
    assert registry._register_order == 1


@pytest.mark.parametrize(("name", "between", "expected"), [
    ("first", (None, "last"), ["middle", "first", "last"]),
    ("last", ("first", None), ["first", "last", "middle"]),
    ("middle", ("first", "last"), ["first", "middle", "last"]),
    ("first", None, ["middle", "last", "first"]),
])
def test_replacement_repositions_without_duplicate_bucket_records(name, between, expected):
    registry = APIX_HANDLER_REGISTRY
    for existing in ["first", "middle", "last"]:
        registry.register_handler(make_entry(existing))
    registry.register_handler(make_entry(name, priority=None if between else 1,
                                        between_handlers=between), exist_ok=True)
    assert registry.priority_buckets == {1: expected}
    assert registry.get_handlers_chain_for_event("event.one") == expected


def test_removed_public_apis_and_event_version_are_absent():
    import inspect
    import apix.core.event as api
    assert not hasattr(api, "delete_handler_from_registry")
    assert not hasattr(APIX_HANDLER_REGISTRY, "get_current_version_for_event")
    assert not hasattr(APIX_HANDLER_REGISTRY, "get_current_version_for_event_without_resolve")
    assert "event_names" not in inspect.signature(unsubscribe).parameters
    assert "version" not in inspect.signature(APIX_HANDLER_REGISTRY.get_handlers_chain_for_event).parameters
    assert "_handler_chain_version" not in ApixEvent.__dataclass_fields__


@pytest.fixture
async def runtime(monkeypatch):
    """Use real consumer scheduling with a private pipe and registry state."""
    from apix.core.event import event_loop, event_pipe
    pipe = ApixEventPipe(remote_enabled=False)
    loop = ApixEventLoop(APIX_HANDLER_REGISTRY)
    monkeypatch.setattr(event_loop, "EVENT_PIPE", pipe)
    monkeypatch.setattr(event_pipe, "EVENT_PIPE", pipe)
    monkeypatch.setattr(event_loop, "APIX_EVENT_LOOP", loop)
    yield pipe, loop
    await loop.stop()
    tasks = list(loop._dispatch_tasks | loop._background_handler_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("publish", ["post", "put", "nowait"])
@pytest.mark.parametrize("cached", [False, True])
async def test_publish_does_not_resolve_but_dequeue_uses_latest_registration(runtime, publish, cached):
    pipe, loop = runtime
    registry = APIX_HANDLER_REGISTRY
    calls = []
    @subscribe("event.*")
    async def first(event):
        calls.append("first")
    if cached:
        registry.get_handlers_chain_for_event("event.one")
        # Expire an existing populated cache before publishing.
        subscribe("event.*", priority=1)(first)
        assert registry.cached_chain["event.one"] is None
    loop._dispatch_semaphore = asyncio.Semaphore(0)
    with patch.object(registry, "get_handlers_chain_for_event",
                      wraps=registry.get_handlers_chain_for_event) as resolve:
        event = ApixEvent("id", EventType.INFO, "event.one", None, 0)
        if publish == "post":
            await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
        elif publish == "put":
            await pipe.put(event)
        else:
            pipe.put_nowait(event)
        assert loop.started
        resolve.assert_not_called()
        @subscribe("event.*", priority=10)
        async def late(event):
            calls.append("late")
        loop._dispatch_semaphore.release()
        await asyncio.wait_for(pipe.join(), 1)
        resolve.assert_called_once_with("event.one")
    assert calls == ["late", "first"]
    assert registry.cached_chain["event.one"] == ["late", "first"]


async def test_dequeue_resolves_chain_before_dispatch_task_starts(runtime, monkeypatch):
    pipe, loop = runtime
    registry = APIX_HANDLER_REGISTRY
    called = []
    @subscribe("event.*")
    async def first(event):
        called.append("first")
    dispatch_started, release = asyncio.Event(), asyncio.Event()
    dispatch = loop._dispatch_event
    async def delayed_dispatch(event, chain):
        assert registry.cached_chain[event.event_name] is chain
        dispatch_started.set()
        await release.wait()
        return await dispatch(event, chain)
    monkeypatch.setattr(loop, "_dispatch_event", delayed_dispatch)
    await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
    await asyncio.wait_for(dispatch_started.wait(), 1)
    @subscribe("event.*", priority=10)
    async def late(event):
        called.append("late")
    assert registry.cached_chain["event.one"] is None
    release.set()
    await asyncio.wait_for(pipe.join(), 1)
    assert called == ["first"]
    await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
    await asyncio.wait_for(pipe.join(), 1)
    assert called == ["first", "late", "first"]


@pytest.mark.parametrize("change", ["remove", "replace", "reregister"])
@pytest.mark.parametrize(("patterns", "filters", "matches"), [
    (["other.*"], [], False),
    (["event.*"], ["event.[ot]*"], False),
    (["Event.*"], [], False),
    (["event.?ne"], ["event.two"], True),
])
async def test_foreground_dispatch_resolves_current_target_after_await(runtime, change, patterns, filters, matches):
    pipe, loop = runtime
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    @subscribe("event.*", priority=10)
    async def first(event):
        entered.set()
        await release.wait()
        calls.append("first-done")
    @subscribe("event.*")
    async def target(event):
        calls.append("old")
    await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
    await asyncio.wait_for(entered.wait(), 1)
    if change in ("remove", "reregister"):
        unsubscribe("target")
    if change in ("replace", "reregister"):
        async def replacement(event):
            calls.append("new")
        replacement.__name__ = "target"
        # Candidate order is fixed, but current matching is checked on invocation.
        subscribe(*patterns, filter_event=filters, priority=100)(replacement)
    unsubscribe("first")
    release.set()
    await asyncio.wait_for(pipe.join(), 1)
    assert calls == (["first-done", "new"] if change != "remove" and matches else ["first-done"])


class NotifyingSemaphore(asyncio.BoundedSemaphore):
    """Expose when task creation reaches its capacity wait."""

    def __init__(self, value):
        super().__init__(value)
        self.waiting = asyncio.Event()

    async def acquire(self):
        self.waiting.set()
        return await super().acquire()


@pytest.mark.parametrize("change", ["remove", "replace"])
@pytest.mark.parametrize(("patterns", "filters", "matches"), [
    (["other.*"], [], False),
    (["event.*"], ["event.[ot]*"], False),
    (["Event.*"], [], False),
    (["event.?ne"], ["event.two"], True),
])
async def test_background_resolves_current_target_after_capacity_wait(runtime, change, patterns, filters, matches):
    pipe, loop = runtime
    capacity = NotifyingSemaphore(1)
    await capacity.acquire()
    capacity.waiting.clear()
    loop._background_handler_semaphore = capacity
    old, new = AsyncMock(), AsyncMock()
    entry = ApixEventHandler(old, background=True)
    entry.name = "target"
    subscribe("event.*")(entry)
    await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
    await asyncio.wait_for(capacity.waiting.wait(), 1)
    assert not loop._background_handler_tasks
    old.assert_not_awaited()
    if change == "remove":
        unsubscribe("target")
    else:
        replacement = ApixEventHandler(new, background=True)
        replacement.name = "target"
        subscribe(*patterns, filter_event=filters)(replacement)
    capacity.release()
    await asyncio.wait_for(pipe.join(), 1)
    await asyncio.wait_for(asyncio.gather(*loop._background_handler_tasks), 1)
    old.assert_not_awaited()
    assert new.await_count == (1 if change == "replace" and matches else 0)


@pytest.mark.parametrize("background", [False, True])
async def test_stop_preserves_started_calls_and_next_publication_restarts(runtime, background):
    pipe, loop = runtime
    entered, release = asyncio.Event(), asyncio.Event()
    completed = []
    @subscribe("event.*", background=background)
    async def target(event):
        entered.set()
        await release.wait()
        completed.append(event.event_name)
    await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
    await asyncio.wait_for(entered.wait(), 1)
    # Bypass publication to leave an event queued while the consumer is stopped.
    await loop.stop()
    assert not loop.started
    pipe.get_channel("builtin").put_nowait(
        ApixEvent("queued", EventType.INFO, "event.two", None, 0)
    )
    unsubscribe("target")
    release.set()
    await asyncio.wait_for(asyncio.gather(*loop._dispatch_tasks,
                                         *loop._background_handler_tasks), 1)
    assert completed == ["event.one"]
    assert pipe.qsize() == 1
    @subscribe("event.*")
    async def current(event):
        completed.append(event.event_name)
    await pipe.post_event(event_type=EventType.INFO, event_name="event.three")
    assert loop.started
    await asyncio.wait_for(pipe.join(), 1)
    assert completed == ["event.one", "event.two", "event.three"]


@pytest.mark.parametrize("timeout", [0, -1])
def test_replacement_can_disable_existing_instance_timeout(timeout):
    entry = ApixEventHandler(AsyncMock(), time_out=30)
    entry.name = "handler"
    subscribe("event.*")(entry)
    subscribe("event.*", time_out=timeout)(entry)
    assert APIX_HANDLER_REGISTRY.get_handler("handler").time_out is None


async def test_publication_starts_consumer_before_waiting_for_queue_capacity(runtime):
    pipe, loop = runtime
    from apix.core.event import BuiltinChannel
    pipe._event_pipe["builtin"] = BuiltinChannel(maxsize=1)
    pipe.get_channel("builtin").put_nowait(
        ApixEvent("first", EventType.INFO, "event.one", None, 0)
    )
    assert not loop.started
    await asyncio.wait_for(pipe.post_event(event_type=EventType.INFO,
                                          event_name="event.two"), 1)
    await asyncio.wait_for(pipe.join(), 1)
    assert loop.started


async def test_reordering_existing_name_only_changes_subsequent_dequeued_order(runtime):
    pipe, loop = runtime
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    @subscribe("event.*", priority=10)
    async def first(event):
        entered.set()
        await release.wait()
        calls.append("first")
    @subscribe("event.*", priority=5)
    async def second(event):
        calls.append("second")
    @subscribe("event.*", priority=1)
    async def third(event):
        calls.append("third")
    await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
    await asyncio.wait_for(entered.wait(), 1)
    subscribe("event.*", priority=20)(third)
    release.set()
    await asyncio.wait_for(pipe.join(), 1)
    assert calls == ["first", "second", "third"]
    calls.clear()
    await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
    await asyncio.wait_for(pipe.join(), 1)
    assert calls == ["third", "first", "second"]


async def test_chain_resolution_failure_acknowledges_event_and_keeps_consuming(runtime):
    pipe, loop = runtime
    with patch.object(APIX_HANDLER_REGISTRY, "get_handlers_chain_for_event",
                      side_effect=[RuntimeError("resolution failed"), []]) as resolve:
        with patch("apix.core.event.event_loop.logger") as logger:
            await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
            await pipe.post_event(event_type=EventType.INFO, event_name="event.two")
            await asyncio.wait_for(pipe.join(), 1)
            assert resolve.call_count == 2
            logger.error.assert_called_once()
    await loop.stop()
    assert loop._dispatch_semaphore._value == 1000


def test_subscribe_defers_validation_to_one_registry_pass():
    registry = APIX_HANDLER_REGISTRY
    with patch.object(registry, "_normalise_patterns",
                      wraps=registry._normalise_patterns) as normalise:
        decorator = subscribe("event.*", "event.*", filter_event=["event.skip"])
        normalise.assert_not_called()
        entry = make_entry("handler")
        assert decorator(entry) is entry
        assert normalise.call_count == 2  # One pass each for subscriptions and filters.
        assert entry.subscribe == ["event.*"]
        assert entry.filter_event == ["event.skip"]


def test_boundary_validation_runs_once_before_registration():
    registry = APIX_HANDLER_REGISTRY
    registry.register_handler(make_entry("left", priority=10))
    registry.register_handler(make_entry("right", priority=1))
    with patch.object(registry, "_validate_between_handlers",
                      wraps=registry._validate_between_handlers) as resolve:
        decorator = subscribe("event.*", between_handlers=("left", "right"))
        resolve.assert_not_called()
        decorator(make_entry("middle"))
        resolve.assert_called_once_with(("left", "right"), handler_name="middle")
    assert registry.get_handlers_chain_for_event("event.one") == ["left", "middle", "right"]


def test_unregister_missing_ok_preserves_existing_cache():
    registry = APIX_HANDLER_REGISTRY
    registry.register_handler(make_entry("existing"))
    chain = registry.get_handlers_chain_for_event("event.one")
    registry.unregister_handler("missing", missing_ok=True)
    assert registry.cached_chain["event.one"] is chain
    assert registry.priority_buckets == {1: ["existing"]}


async def test_dispatch_cancelled_before_start_releases_ack_and_capacity(runtime):
    pipe, loop = runtime
    cancelled = []
    class CancelFirstTask(set):
        def add(self, task):
            super().add(task)
            if not cancelled:
                cancelled.append(task)
                task.cancel()  # Cancel before create_task can enter the coroutine.
    loop._dispatch_tasks = CancelFirstTask()
    loop._dispatch_semaphore = asyncio.BoundedSemaphore(1)
    calls = []
    @subscribe("event.*")
    async def handler(event):
        calls.append(event.event_name)
    with patch.object(pipe, "task_done", wraps=pipe.task_done) as acknowledge:
        await pipe.post_event(event_type=EventType.INFO, event_name="event.first")
        await pipe.post_event(event_type=EventType.INFO, event_name="event.second")
        await asyncio.wait_for(pipe.join(), 1)
        await loop.stop()
        assert acknowledge.call_count == 2
    assert cancelled[0].cancelled()
    assert calls == ["event.second"]
    assert not loop._dispatch_tasks
    assert loop._dispatch_semaphore._value == 1


@pytest.mark.parametrize("outcome", ["return", "raise", "cancel"])
async def test_started_dispatch_completes_queue_and_capacity_exactly_once(runtime, outcome):
    pipe, loop = runtime
    entered, release = asyncio.Event(), asyncio.Event()
    loop._dispatch_semaphore = asyncio.BoundedSemaphore(1)
    @subscribe("event.*")
    async def handler(event):
        entered.set()
        await release.wait()
        if outcome == "raise":
            raise ValueError("handler failed")
    with patch.object(pipe, "task_done", wraps=pipe.task_done) as acknowledge:
        await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
        await asyncio.wait_for(entered.wait(), 1)
        if outcome == "cancel":
            next(iter(loop._dispatch_tasks)).cancel()
        else:
            release.set()
        await asyncio.wait_for(pipe.join(), 1)
        await loop.stop()
        acknowledge.assert_called_once_with()
    assert not loop._dispatch_tasks
    assert loop._dispatch_semaphore._value == 1


@pytest.mark.parametrize("phase", ["before_start", "waiting", "running"])
async def test_background_cancellation_only_releases_acquired_capacity(runtime, phase):
    pipe, loop = runtime
    entered = asyncio.Event()
    capacity = NotifyingSemaphore(1)
    loop._background_handler_semaphore = capacity
    cancelled = []
    class CancelOnAdd(set):
        def add(self, task):
            super().add(task)
            cancelled.append(task)
            task.cancel()
    if phase == "before_start":
        loop._background_handler_tasks = CancelOnAdd()
    elif phase == "waiting":
        await capacity.acquire()
        capacity.waiting.clear()
    @subscribe("event.*", background=True)
    async def handler(event):
        entered.set()
        await asyncio.Event().wait()
    with patch.object(pipe, "task_done", wraps=pipe.task_done) as acknowledge:
        await pipe.post_event(event_type=EventType.INFO, event_name="event.one")
        if phase == "waiting":
            await asyncio.wait_for(capacity.waiting.wait(), 1)
            assert not loop._background_handler_tasks
            tasks = list(loop._dispatch_tasks)
        else:
            await asyncio.wait_for(pipe.join(), 1)
            if phase == "running":
                await asyncio.wait_for(entered.wait(), 1)
            tasks = cancelled or list(loop._background_handler_tasks)
        assert len(tasks) == 1
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.wait_for(pipe.join(), 1)
        acknowledge.assert_called_once_with()
    assert entered.is_set() == (phase == "running")
    assert not loop._background_handler_tasks
    if phase == "waiting":
        assert loop._background_handler_semaphore._value == 0
        loop._background_handler_semaphore.release()
    assert loop._background_handler_semaphore._value == 1
