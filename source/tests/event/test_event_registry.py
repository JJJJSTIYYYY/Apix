"""
Tests for event_registry module.

Covers ApixEventRegistry: singleton, handler registration, insertion ordering,
error handling, and metadata retrieval.
"""

import pytest

from apix.core.event.base import ApixEvent, HandlerEntry
from apix.common.type import (
    EventHandlerNotRegistered,
    EventHandlerAlreadyRegistered,
)
from apix.core.event.event_registry import ApixEventRegistry, apix_event_registry


# ============================
# Helpers
# ============================

def _reset_registry(registry: ApixEventRegistry):
    """Reset a registry instance to a clean state for isolated tests."""
    registry._handlers.clear()
    registry._handlers_meta.clear()
    registry._register_order = 0


# ============================
# Tests: Singleton
# ============================


class TestEventRegistrySingleton:
    """Tests for singleton behavior."""

    def test_class_level_singleton(self):
        """ApixEventRegistry should return the same instance via __new__."""
        r1 = ApixEventRegistry()
        r2 = ApixEventRegistry()
        assert r1 is r2

    def test_instance_attribute_isolation_concept(self):
        """Verify _instance is stored at class level."""
        assert ApixEventRegistry._instance is not None

    def test_module_level_event_registry_is_singleton(self):
        """Module-level apix_event_registry should be an ApixEventRegistry instance."""
        assert isinstance(apix_event_registry, ApixEventRegistry)

    def test_reinitializing_singleton_preserves_registered_handlers(self):
        """Calling the constructor again must not reset singleton state."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def preserved_handler(event: ApixEvent):
            pass

        registry.subscribe("test.event")(preserved_handler)

        same_registry = ApixEventRegistry()

        assert same_registry is registry
        assert [
            handler.name
            for handler in same_registry.get_handlers("test.event")
        ] == ["preserved_handler"]

        _reset_registry(registry)


# ============================
# Tests: _find_insert_index
# ============================


class TestFindInsertIndex:
    """Tests for _find_insert_index method."""

    EVENT_NAME = "test.event"

    def _make_entries(self, names_and_priorities):
        """Create HandlerEntry list from (name, priority) pairs."""
        entries = []

        for i, (name, priority) in enumerate(names_and_priorities):
            entries.append(
                HandlerEntry(
                    id=f"id_{name}",
                    name=name,
                    subscribe=self.EVENT_NAME,
                    callback=None,
                    priority=priority,
                    register_order=i,
                )
            )

        return entries

    def test_priority_none_returns_end(self):
        """When priority is None and no between, return len(handlers)."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 1.0),
                ("h2", 2.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=None,
        )

        assert idx == len(handlers)

    def test_priority_higher_than_all_returns_zero(self):
        """Highest priority should be inserted at index 0."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 5.0),
                ("h2", 3.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=10.0,
        )

        assert idx == 0

    def test_priority_equal_to_existing(self):
        """Same priority should preserve registration order."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 5.0),
                ("h2", 5.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=5.0,
        )

        assert idx == 2

    def test_priority_between_existing(self):
        """Priority between two values should insert in the correct position."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 10.0),
                ("h2", 5.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=7.0,
        )

        assert idx == 1

    def test_priority_lower_than_all_returns_end(self):
        """Lowest priority should be inserted at the end."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 10.0),
                ("h2", 5.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=1.0,
        )

        assert idx == 2

    def test_between_handlers_adjacent_boundaries(self):
        """
        When the boundaries are adjacent, insert immediately before
        the right boundary.
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("left_h", 10.0),
                ("right_h", 5.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=None,
            between_handlers=("left_h", "right_h"),
        )

        assert idx == 1

    def test_between_handlers_with_existing_middle_handlers(self):
        """
        When other handlers exist between the boundaries, insert immediately
        before the right boundary.

        Existing:
            left_h, middle_a, middle_b, right_h

        Result after handlers.insert(idx, new_handler):
            left_h, middle_a, middle_b, new_handler, right_h
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("left_h", 10.0),
                ("middle_a", 8.0),
                ("middle_b", 5.0),
                ("right_h", 3.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=None,
            between_handlers=("left_h", "right_h"),
        )

        assert idx == 3
        assert handlers[idx].name == "right_h"

    def test_between_handlers_none_left_inserts_before_right(self):
        """
        (None, right_handler) should insert immediately before
        right_handler.
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 10.0),
                ("right_h", 5.0),
                ("h2", 3.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=None,
            between_handlers=(None, "right_h"),
        )

        assert idx == 1
        assert handlers[idx].name == "right_h"

    def test_between_handlers_none_right_inserts_after_left(self):
        """
        (left_handler, None) should insert immediately after
        left_handler.
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 10.0),
                ("left_h", 5.0),
                ("h2", 3.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=None,
            between_handlers=("left_h", None),
        )

        assert idx == 2
        assert handlers[idx - 1].name == "left_h"

    def test_between_handlers_left_at_end_with_none_right(self):
        """
        (left_handler, None) should return len(handlers) when the left
        boundary is the final handler.
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 10.0),
                ("left_h", 5.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=None,
            between_handlers=("left_h", None),
        )

        assert idx == len(handlers)

    def test_between_handlers_right_at_start_with_none_left(self):
        """
        (None, right_handler) should return zero when the right boundary
        is the first handler.
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("right_h", 10.0),
                ("h1", 5.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=None,
            between_handlers=(None, "right_h"),
        )

        assert idx == 0

    def test_between_handlers_left_not_found_raises(self):
        """An unregistered left boundary should raise."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 1.0),
                ("h2", 2.0),
            ]
        )

        with pytest.raises(
            EventHandlerNotRegistered,
            match="nonexistent",
        ) as exc_info:
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=handlers,
                priority=None,
                between_handlers=("nonexistent", "h2"),
            )

        assert self.EVENT_NAME in str(exc_info.value)

    def test_between_handlers_right_not_found_raises(self):
        """An unregistered right boundary should raise."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 1.0),
                ("h2", 2.0),
            ]
        )

        with pytest.raises(
            EventHandlerNotRegistered,
            match="nonexistent",
        ) as exc_info:
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=handlers,
                priority=None,
                between_handlers=("h1", "nonexistent"),
            )

        assert self.EVENT_NAME in str(exc_info.value)

    def test_between_handlers_none_left_right_not_found_raises(self):
        """
        (None, right_handler) should raise when right_handler is not
        registered for the event.
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 1.0),
                ("h2", 2.0),
            ]
        )

        with pytest.raises(
            EventHandlerNotRegistered,
            match="right_h",
        ):
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=handlers,
                priority=None,
                between_handlers=(None, "right_h"),
            )

    def test_between_handlers_none_right_left_not_found_raises(self):
        """
        (left_handler, None) should raise when left_handler is not
        registered for the event.
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 1.0),
                ("h2", 2.0),
            ]
        )

        with pytest.raises(
            EventHandlerNotRegistered,
            match="left_h",
        ):
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=handlers,
                priority=None,
                between_handlers=("left_h", None),
            )

    def test_between_handlers_reversed_boundaries_raise(self):
        """
        When the supplied left boundary appears after the supplied right
        boundary, registration should fail with ValueError.

        Existing:
            right_h, middle_h, left_h

        Invalid:
            between_handlers=("left_h", "right_h")
        """
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("right_h", 10.0),
                ("middle_h", 5.0),
                ("left_h", 3.0),
            ]
        )

        with pytest.raises(
            ValueError,
            match="must be before",
        ):
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=handlers,
                priority=None,
                between_handlers=("left_h", "right_h"),
            )

    def test_between_handlers_same_boundary_raises(self):
        """The same handler cannot be used as both boundaries."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 1.0),
                ("h2", 2.0),
            ]
        )

        with pytest.raises(
            ValueError,
            match="cannot be the same",
        ):
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=handlers,
                priority=None,
                between_handlers=("h1", "h1"),
            )

    def test_between_handlers_both_none_raises(self):
        """(None, None) does not specify an insertion boundary."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", 1.0),
                ("h2", 2.0),
            ]
        )

        with pytest.raises(
            ValueError,
            match=r"\(None, None\)",
        ):
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=handlers,
                priority=None,
                between_handlers=(None, None),
            )

    def test_empty_handlers_priority_none_returns_zero(self):
        """Empty handler list with None priority should return zero."""
        registry = ApixEventRegistry()

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=[],
            priority=None,
        )

        assert idx == 0

    def test_empty_handlers_priority_given_returns_zero(self):
        """Empty handler list with a priority should return zero."""
        registry = ApixEventRegistry()

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=[],
            priority=5.0,
        )

        assert idx == 0

    def test_empty_handlers_with_between_raises(self):
        """
        An empty handler list cannot satisfy a non-None insertion
        boundary.
        """
        registry = ApixEventRegistry()

        with pytest.raises(
            EventHandlerNotRegistered,
            match="left_h",
        ):
            registry._find_insert_index(
                event_name=self.EVENT_NAME,
                handlers=[],
                priority=None,
                between_handlers=("left_h", None),
            )

    def test_priority_with_none_values_in_handlers(self):
        """Handlers with None priority should be skipped during comparison."""
        registry = ApixEventRegistry()
        handlers = self._make_entries(
            [
                ("h1", None),
                ("h2", 5.0),
            ]
        )

        idx = registry._find_insert_index(
            event_name=self.EVENT_NAME,
            handlers=handlers,
            priority=7.0,
        )

        assert idx == 1


# ============================
# Tests: get_handlers
# ============================


class TestGetHandlers:
    """Tests for get_handlers method."""

    def test_get_handlers_empty_registry(self):
        """Should return empty list for unknown event."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        result = registry.get_handlers("nonexistent.event")
        assert result == []

    def test_get_handlers_after_registration(self):
        """Should return registered handlers for an event."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def my_handler(event: ApixEvent):
            pass

        registry.subscribe("test.event", priority=1.0)(my_handler)
        handlers = registry.get_handlers("test.event")
        assert len(handlers) == 1
        assert handlers[0].name == "my_handler"

    def test_get_handlers_multiple_handlers_same_event(self):
        """Multiple handlers for the same event should all be returned."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        async def h2(event: ApixEvent):
            pass

        registry.subscribe("test.event", priority=3.0)(h1)
        registry.subscribe("test.event", priority=1.0)(h2)

        handlers = registry.get_handlers("test.event")
        assert len(handlers) == 2
        # Higher priority first
        assert handlers[0].name == "h1"
        assert handlers[1].name == "h2"


# ============================
# Tests: get_handler_meta
# ============================


class TestGetHandlerMeta:
    """Tests for get_handler_meta method."""

    def test_get_handler_meta_returns_correct_data(self):
        """Should return correct HandlerMeta for registered handler."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def my_handler(event: ApixEvent):
            pass

        registry.subscribe("test.event", priority=2.5)(my_handler)

        meta = registry.get_handler_meta("my_handler")
        assert isinstance(meta, dict)
        assert meta["name"] == "my_handler"
        assert meta["subscribe"] == ["test.event"]
        assert meta["priority"] == 2.5

    def test_get_handler_meta_not_found_raises(self):
        """Should raise EventHandlerNotRegistered for unknown handler."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        with pytest.raises(EventHandlerNotRegistered) as exc_info:
            registry.get_handler_meta("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_get_handler_meta_with_between_handlers(self):
        """Meta should include between data when using between_handlers."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        async def h2(event: ApixEvent):
            pass

        async def h3(event: ApixEvent):
            pass

        registry.subscribe("test.event", priority=3.0)(h1)
        registry.subscribe("test.event", priority=1.0)(h2)
        registry.subscribe("test.event", between_handlers=("h1", "h2"))(h3)

        meta = registry.get_handler_meta("h3")
        assert meta["between"] == ("h1", "h2")
        assert meta["priority"] is None


# ============================
# Tests: get_all_handlers_meta
# ============================


class TestGetAllHandlersMeta:
    """Tests for get_all_handlers_meta method."""

    def test_get_all_handlers_meta_empty(self):
        """Empty registry should return empty dict."""
        registry = ApixEventRegistry()
        _reset_registry(registry)
        result = registry.get_all_handlers_meta()
        assert result == {}

    def test_get_all_handlers_meta_returns_deep_copy(self):
        """Should return a deep copy, not the internal dict."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        registry.subscribe("test.event")(h1)

        result = registry.get_all_handlers_meta()
        assert "h1" in result

        # Mutating result should not affect internal state
        result["new_key"] = {}  # type: ignore
        assert "new_key" not in registry._handlers_meta

    def test_get_all_handlers_meta_multiple_handlers(self):
        """Should return all registered handlers."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        async def h2(event: ApixEvent):
            pass

        registry.subscribe("e1")(h1)
        registry.subscribe("e2")(h2)

        result = registry.get_all_handlers_meta()
        assert len(result) == 2
        assert "h1" in result
        assert "h2" in result


# ============================
# Tests: subscribe decorator
# ============================


class TestOnEventDecorator:
    """Tests for subscribe decorator."""

    def test_on_event_no_event_names_raises(self):
        """Calling subscribe with no event_names should raise ValueError."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        with pytest.raises(ValueError, match="At least one event_name"):
            registry.subscribe()

    @pytest.mark.parametrize(
        "event_names",
        [
            ("",),
            ("event.a", ""),
        ],
    )
    def test_on_event_empty_event_name_raises_without_mutating_registry(
        self, event_names
    ):
        """Every subscribed event name must be non-empty."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        with pytest.raises(ValueError, match="event_name cannot be empty"):
            registry.subscribe(*event_names)

        assert registry._handlers == {}
        assert registry._handlers_meta == {}
        assert registry._register_order == 0

    @pytest.mark.parametrize(
        "between_handlers",
        [
            ["left", "right"],
            ("left",),
            ("left", "middle", "right"),
        ],
    )
    def test_on_event_malformed_between_handlers_raises(
        self, between_handlers
    ):
        """between_handlers must be a two-item tuple."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        with pytest.raises(ValueError, match="exactly two handler names"):
            registry.subscribe(
                "test.event",
                between_handlers=between_handlers,
            )

    def test_on_event_between_handlers_both_none_raises_before_decoration(self):
        registry = ApixEventRegistry()
        _reset_registry(registry)

        with pytest.raises(ValueError, match=r"cannot be \(None, None\)"):
            registry.subscribe(
                "test.event",
                between_handlers=(None, None),
            )

        assert registry._register_order == 0

    def test_on_event_between_handlers_same_name_raises_before_decoration(self):
        registry = ApixEventRegistry()
        _reset_registry(registry)

        with pytest.raises(ValueError, match="cannot be the same handler"):
            registry.subscribe(
                "test.event",
                between_handlers=("same", "same"),
            )

        assert registry._register_order == 0

    def test_on_event_basic_registration(self):
        """Basic registration: handler is registered and returned unchanged."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def my_handler(event: ApixEvent):
            pass

        decorated = registry.subscribe("test.event")(my_handler)
        assert decorated is my_handler

        handlers = registry.get_handlers("test.event")
        assert len(handlers) == 1
        assert handlers[0].name == "my_handler"

    def test_on_event_multiple_event_names(self):
        """A handler can be registered for multiple events."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def multi_handler(event: ApixEvent):
            pass

        registry.subscribe("event.a", "event.b", "event.c")(multi_handler)

        for event_name in ["event.a", "event.b", "event.c"]:
            handlers = registry.get_handlers(event_name)
            assert len(handlers) == 1
            assert handlers[0].name == "multi_handler"

    def test_on_event_duplicate_event_names_are_registered_once(self):
        """Duplicate event arguments retain first-seen order without duplication."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def multi_handler(event: ApixEvent):
            pass

        registry.subscribe(
            "event.b",
            "event.a",
            "event.b",
            "event.a",
        )(multi_handler)

        assert [h.name for h in registry.get_handlers("event.a")] == [
            "multi_handler"
        ]
        assert [h.name for h in registry.get_handlers("event.b")] == [
            "multi_handler"
        ]
        assert registry.get_handler_meta("multi_handler")["subscribe"] == [
            "event.b",
            "event.a",
        ]
        assert registry._register_order == 1

    def test_on_event_duplicate_handler_is_ignored_by_default(self):
        """Default duplicate registration keeps the existing handler."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def original_handler(event: ApixEvent):
            pass

        async def replacement_handler(event: ApixEvent):
            pass

        original_handler.__name__ = "same_handler"
        replacement_handler.__name__ = "same_handler"

        registry.subscribe("event.a", priority=3)(original_handler)
        original_entry = registry.get_handlers("event.a")[0]
        original_meta = registry.get_all_handlers_meta()["same_handler"]

        decorated = registry.subscribe(
            "event.a",
            priority=1,
            stop_when_error=False,
            background=True,
        )(replacement_handler)

        assert decorated is replacement_handler
        assert registry.get_handlers("event.a") == [original_entry]
        assert registry.get_handlers("event.a")[0].callback is original_handler
        assert registry.get_all_handlers_meta()["same_handler"] == original_meta
        assert registry._register_order == 1

    def test_on_event_duplicate_handler_raises_when_exist_ok_is_false(self):
        """Strict duplicate registration raises without changing state."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def my_handler(event: ApixEvent):
            pass

        registry.subscribe("event.a")(my_handler)

        with pytest.raises(EventHandlerAlreadyRegistered) as exc_info:
            registry.subscribe("event.a", exist_ok=False)(my_handler)
        assert "my_handler" in str(exc_info.value)
        assert [
            handler.name
            for handler in registry.get_handlers("event.a")
        ] == ["my_handler"]
        assert registry._register_order == 1

    def test_on_event_multiple_events_registration_is_atomic(self):
        """A failed boundary on one event must not partially register another."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def left(event: ApixEvent):
            pass

        async def right(event: ApixEvent):
            pass

        async def candidate(event: ApixEvent):
            pass

        registry.subscribe("event.a", "event.b")(left)
        registry.subscribe("event.a")(right)
        register_order = registry._register_order

        with pytest.raises(EventHandlerNotRegistered, match="right"):
            registry.subscribe(
                "event.a",
                "event.b",
                between_handlers=("left", "right"),
            )(candidate)

        assert [h.name for h in registry.get_handlers("event.a")] == [
            "left",
            "right",
        ]
        assert [h.name for h in registry.get_handlers("event.b")] == ["left"]
        assert "candidate" not in registry._handlers_meta
        assert registry._register_order == register_order

    def test_on_event_between_handlers_applies_to_every_subscribed_event(self):
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def left(event: ApixEvent):
            pass

        async def right(event: ApixEvent):
            pass

        async def middle(event: ApixEvent):
            pass

        registry.subscribe("event.a", "event.b", priority=3)(left)
        registry.subscribe("event.a", "event.b", priority=1)(right)
        registry.subscribe(
            "event.a",
            "event.b",
            between_handlers=("left", "right"),
        )(middle)

        for event_name in ("event.a", "event.b"):
            handlers = registry.get_handlers(event_name)
            assert [handler.name for handler in handlers] == [
                "left",
                "middle",
                "right",
            ]
            assert handlers[1].priority is None

        first_entry = registry.get_handlers("event.a")[1]
        second_entry = registry.get_handlers("event.b")[1]
        assert first_entry.id != second_entry.id
        assert first_entry.register_order == second_entry.register_order

    def test_on_event_default_priority_is_1(self):
        """Default priority should be 1 when not specified."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        registry.subscribe("test.event")(h1)
        meta = registry.get_handler_meta("h1")
        assert meta["priority"] == 1

    def test_on_event_priority_ordering(self):
        """Handlers should be ordered by priority (higher first)."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def low(event: ApixEvent):
            pass

        async def high(event: ApixEvent):
            pass

        async def mid(event: ApixEvent):
            pass

        registry.subscribe("test.event", priority=1.0)(low)
        registry.subscribe("test.event", priority=10.0)(high)
        registry.subscribe("test.event", priority=5.0)(mid)

        handlers = registry.get_handlers("test.event")
        assert [h.name for h in handlers] == ["high", "mid", "low"]

    def test_on_event_same_priority_registration_order(self):
        """Same priority handlers should keep registration order."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def first(event: ApixEvent):
            pass

        async def second(event: ApixEvent):
            pass

        async def third(event: ApixEvent):
            pass

        registry.subscribe("test.event", priority=1.0)(first)
        registry.subscribe("test.event", priority=1.0)(second)
        registry.subscribe("test.event", priority=1.0)(third)

        handlers = registry.get_handlers("test.event")
        assert [h.name for h in handlers] == ["first", "second", "third"]

    def test_on_event_timeout_zero_becomes_negative_one(self):
        """time_out <= 0 should be converted to -1 (no timeout)."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h(event: ApixEvent):
            pass

        registry.subscribe("test.event", time_out=0)(h)
        meta = registry.get_handler_meta("h")
        assert meta["time_out"] == -1

    def test_on_event_timeout_defaults_to_infinite_wait(self):
        """Omitting time_out should store the no-timeout sentinel."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h(event: ApixEvent):
            pass

        registry.subscribe("test.event")(h)

        assert registry.get_handler_meta("h")["time_out"] == -1

    def test_on_event_timeout_negative_becomes_negative_one(self):
        """time_out < 0 should be converted to -1."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h(event: ApixEvent):
            pass

        registry.subscribe("test.event", time_out=-5)(h)
        meta = registry.get_handler_meta("h")
        assert meta["time_out"] == -1

    def test_on_event_background_flag(self):
        """background=True should be stored in meta."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def bg_handler(event: ApixEvent):
            pass

        registry.subscribe("test.event", background=True)(bg_handler)
        meta = registry.get_handler_meta("bg_handler")
        assert meta["background"] is True

    def test_on_event_stop_when_error_flag(self):
        """stop_when_error should be stored in meta."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h(event: ApixEvent):
            pass

        registry.subscribe("test.event", stop_when_error=False)(h)
        meta = registry.get_handler_meta("h")
        assert meta["stop_when_error"] is False

    def test_on_event_between_handlers_overrides_priority(self):
        """When both between_handlers and priority are given, priority is set to None."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        async def h2(event: ApixEvent):
            pass

        async def h3(event: ApixEvent):
            pass

        registry.subscribe("test.event", priority=3.0)(h1)
        registry.subscribe("test.event", priority=1.0)(h2)
        registry.subscribe("test.event", between_handlers=("h1", "h2"), priority=5.0)(h3)

        meta = registry.get_handler_meta("h3")
        assert meta["priority"] is None
        assert meta["between"] == ("h1", "h2")

    def test_on_event_different_events_independent_ordering(self):
        """
        Handler order is independent per event.
        Each event maintains its own handler list with independent priorities.
        """
        registry = ApixEventRegistry()
        _reset_registry(registry)

        # Register different handlers for different events to verify
        # per-event ordering is independent.
        async def h1(event: ApixEvent):
            pass

        async def h2(event: ApixEvent):
            pass

        async def h3(event: ApixEvent):
            pass

        async def h4(event: ApixEvent):
            pass

        # event.1: h1 (priority 5) → h2 (priority 1)
        registry.subscribe("event.1", priority=5.0)(h1)
        registry.subscribe("event.1", priority=1.0)(h2)

        # event.2: h3 (priority 1) → h4 (priority 5)
        registry.subscribe("event.2", priority=1.0)(h3)
        registry.subscribe("event.2", priority=5.0)(h4)

        h1_handlers = registry.get_handlers("event.1")
        h2_handlers = registry.get_handlers("event.2")

        # event.1: h1 (prio=5) before h2 (prio=1)
        assert [h.name for h in h1_handlers] == ["h1", "h2"]
        # event.2: h4 (prio=5) before h3 (prio=1)
        assert [h.name for h in h2_handlers] == ["h4", "h3"]

    def test_on_event_register_order_increment(self):
        """register_order should increment across registrations."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        async def h2(event: ApixEvent):
            pass

        registry.subscribe("e1")(h1)
        registry.subscribe("e2")(h2)

        meta1 = registry.get_handler_meta("h1")
        meta2 = registry.get_handler_meta("h2")
        assert meta2["register_order"] > meta1["register_order"]

    def test_on_event_multiple_events_same_handler_different_priorities(self):
        """Priority is per-handler, not per-event."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h(event: ApixEvent):
            pass

        registry.subscribe("event.a", "event.b", priority=5.0)(h)

        meta = registry.get_handler_meta("h")
        assert meta["priority"] == 5.0
        assert set(meta["subscribe"]) == {"event.a", "event.b"}


# ============================
# Tests: HandlerEntry attributes
# ============================


class TestHandlerEntryAttributes:
    """Verify HandlerEntry has expected attributes after registration."""

    def test_handler_entry_has_unique_id(self):
        """Each handler entry should have a unique id."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def h1(event: ApixEvent):
            pass

        async def h2(event: ApixEvent):
            pass

        registry.subscribe("test.event")(h1)
        registry.subscribe("test.event")(h2)

        handlers = registry.get_handlers("test.event")
        assert len(handlers) == 2
        assert handlers[0].id != handlers[1].id

    def test_handler_entry_callback_is_original_function(self):
        """HandlerEntry.callback should be the original async function."""
        registry = ApixEventRegistry()
        _reset_registry(registry)

        async def my_handler(event: ApixEvent):
            pass

        registry.subscribe("test.event")(my_handler)

        handlers = registry.get_handlers("test.event")
        assert handlers[0].callback is my_handler
