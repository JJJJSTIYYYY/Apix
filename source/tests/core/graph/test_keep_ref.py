"""Tests for reference-preserving graph state fields."""

import asyncio
from typing import Annotated, Any, TypedDict

import pytest
import pytest_asyncio

from apix.core.event.event_loop import APIX_EVENT_LOOP
from apix.core.event import EVENT_PIPE
from apix.core.graph import (
    AutoMerge,
    Command,
    END,
    GraphManager,
    KeepRef,
    NodeGraph,
    START,
)
from apix.core.graph.base import _copy_state, get_keep_ref_keys
from apix.core.graph.context import GraphContext


@pytest_asyncio.fixture(
    autouse=True,
    scope="module",
    loop_scope="session",
)
async def stop_event_runtime_after_module():
    yield
    await APIX_EVENT_LOOP.stop()
    await EVENT_PIPE.clear()


class UncopyableResource:
    """Mutable runtime resource that intentionally cannot be deep-copied."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def __deepcopy__(self, memo):
        raise AssertionError("KeepRef value must not be deep-copied")


class ReferenceAccumulator:
    """AutoMerge value whose addition mutates and returns the same object."""

    def __init__(self, values: list[str]) -> None:
        self.values = list(values)
        self.additions: list[list[str]] = []

    def __add__(self, values: list[str]) -> "ReferenceAccumulator":
        self.additions.append(list(values))
        self.values.extend(values)
        return self

    def __deepcopy__(self, memo):
        raise AssertionError("AutoMerge + KeepRef value must not be deep-copied")


class KeepRefState(TypedDict, total=False):
    resource: Annotated[UncopyableResource, KeepRef()]
    class_marker: Annotated[list[str], KeepRef]
    messages: Annotated[list[str], AutoMerge(), KeepRef()]
    ordinary: dict[str, Any]
    ignored: Annotated[list[str], "ordinary metadata"]


class CombinedMarkerState(TypedDict):
    accumulator: Annotated[
        ReferenceAccumulator,
        AutoMerge(),
        KeepRef(),
    ]


def _context(
    state: dict[str, Any],
    state_schema: type | None = None,
) -> GraphContext:
    context = GraphContext(state_schema)
    context.state = state
    return context


def test_get_keep_ref_keys_supports_instance_and_class_markers():
    """Both documented marker forms are discovered, including mixed metadata."""
    assert get_keep_ref_keys(KeepRefState) == frozenset(
        {"resource", "class_marker", "messages"}
    )
    assert get_keep_ref_keys(None) == frozenset()


def test_get_keep_ref_keys_rejects_non_class_schema():
    """Schema validation mirrors AutoMerge discovery."""
    with pytest.raises(TypeError, match="state_schema.*class or None"):
        get_keep_ref_keys({})


def test_copy_state_skips_deepcopy_for_marked_resource():
    """KeepRef works for resources whose copy protocol is deliberately disabled."""
    resource = UncopyableResource()
    ordinary = {"nested": [1]}
    copied = _copy_state(
        {
            "resource": resource,
            "ordinary": ordinary,
        },
        get_keep_ref_keys(KeepRefState),
    )

    assert copied["resource"] is resource
    assert copied["ordinary"] == ordinary
    assert copied["ordinary"] is not ordinary
    assert copied["ordinary"]["nested"] is not ordinary["nested"]


def test_copy_state_applies_keep_ref_per_field_not_per_object():
    """An unmarked alias is still copied even when a marked field shares it."""
    shared: list[str] = ["value"]
    copied = _copy_state(
        {
            "class_marker": shared,
            "ordinary": shared,
        },
        get_keep_ref_keys(KeepRefState),
    )

    assert copied["class_marker"] is shared
    assert copied["ordinary"] == shared
    assert copied["ordinary"] is not shared
    assert list(copied) == ["class_marker", "ordinary"]


def test_copy_state_without_present_marked_fields_remains_normal_deepcopy():
    """A schema marker does not alter unrelated or absent state fields."""
    original = {"ordinary": {"values": [1]}}
    copied = _copy_state(
        original,
        get_keep_ref_keys(KeepRefState),
    )

    assert copied == original
    assert copied is not original
    assert copied["ordinary"] is not original["ordinary"]


def test_copy_state_rejects_non_dictionary_input():
    with pytest.raises(TypeError, match="Graph state must be a dict"):
        _copy_state([], get_keep_ref_keys(KeepRefState))


def test_apply_command_preserves_explicit_keep_ref_update():
    """Returning a marked field explicitly must not copy its new value."""
    original_resource = UncopyableResource()
    replacement_resource = UncopyableResource()
    graph = NodeGraph({}, {START: END}, state_schema=KeepRefState)

    state, next_node = graph.apply_command(
        Command(
            update={
                "resource": replacement_resource,
                "ordinary": {"values": []},
            }
        ),
        START,
        _context(
            {"resource": original_resource},
            KeepRefState,
        ),
    )

    assert state["resource"] is replacement_resource
    assert state["ordinary"] == {"values": []}
    assert next_node == END


@pytest.mark.asyncio(loop_scope="session")
async def test_keep_ref_survives_complete_multi_node_graph_invocation():
    """Nodes can mutate one shared resource while ordinary input stays isolated."""
    resource = UncopyableResource()
    original = {
        "resource": resource,
        "messages": ["user"],
        "ordinary": {"nested": ["caller"]},
    }
    seen_ids: list[int] = []

    def first(state: dict[str, Any]) -> Command:
        seen_ids.append(id(state["resource"]))
        state["resource"].events.append("first")
        state["ordinary"]["nested"].append("node-only")
        return Command(update={"messages": ["first"]})

    def second(state: dict[str, Any]) -> dict[str, Any]:
        seen_ids.append(id(state["resource"]))
        state["resource"].events.append("second")
        # Returning the resource locks down KeepRef handling in Command.update.
        return {
            "resource": state["resource"],
            "messages": ["second"],
        }

    graph = (
        GraphManager(KeepRefState)
        .add_nodes([first, second])
        .add_edge(START, "first")
        .add_edge("first", "second")
        .compile_graph()
    )

    result = await graph.invoke(original)

    assert seen_ids == [id(resource), id(resource)]
    assert result["resource"] is resource
    assert result["resource"].events == ["first", "second"]
    assert result["messages"] == ["user", "first", "second"]
    assert original["ordinary"] == {"nested": ["caller"]}
    assert result["ordinary"] == {"nested": ["caller"]}


@pytest.mark.asyncio(loop_scope="session")
async def test_auto_increase_and_keep_ref_work_on_the_same_state_field():
    """A shared accumulator is never copied and receives every additive update."""
    accumulator = ReferenceAccumulator(["initial"])
    seen_references: list[ReferenceAccumulator] = []

    def first(state: dict[str, Any]) -> Command:
        seen_references.append(state["accumulator"])
        state["accumulator"].values.append("direct")
        return Command(update={"accumulator": ["first-update"]})

    def second(state: dict[str, Any]) -> Command:
        seen_references.append(state["accumulator"])
        return Command(update={"accumulator": ["second-update"]})

    graph = (
        GraphManager(CombinedMarkerState)
        .add_nodes([first, second])
        .add_edge(START, "first")
        .add_edge("first", "second")
        .compile_graph()
    )

    context = GraphContext(CombinedMarkerState)
    assert context._keep_ref_keys == frozenset({"accumulator"})
    assert context._auto_increase_keys == frozenset({"accumulator"})

    result = await graph.invoke({"accumulator": accumulator})

    assert seen_references == [accumulator, accumulator]
    assert result["accumulator"] is accumulator
    assert accumulator.values == [
        "initial",
        "direct",
        "first-update",
        "second-update",
    ]
    assert accumulator.additions == [
        ["first-update"],
        ["second-update"],
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_context_abort_uses_the_graph_keep_ref_snapshotter():
    """Direct abort preserves graph-specific state snapshot semantics."""
    resource = UncopyableResource()
    node_started = asyncio.Event()
    release_node = asyncio.Event()
    node_finished = asyncio.Event()

    async def waiting_node(state: dict[str, Any]) -> dict[str, Any]:
        node_started.set()
        await release_node.wait()
        node_finished.set()
        return {}

    graph = (
        GraphManager(KeepRefState)
        .add_node(waiting_node)
        .add_edge(START, "waiting_node")
        .compile_graph()
    )
    context = GraphContext()
    invocation = asyncio.create_task(
        graph.invoke(
            {
                "resource": resource,
                "ordinary": {"nested": [1]},
            },
            context,
        )
    )

    await asyncio.wait_for(node_started.wait(), timeout=1)
    context.abort()
    result = await asyncio.wait_for(invocation, timeout=1)

    assert result["resource"] is resource
    assert result["ordinary"] == {"nested": [1]}

    release_node.set()
    await asyncio.wait_for(node_finished.wait(), timeout=1)
