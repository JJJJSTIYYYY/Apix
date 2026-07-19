"""Behaviour tests for the event-driven graph runtime."""

import asyncio

import pytest
import pytest_asyncio

from apix.core.event.event_loop import apix_event_loop
from apix.core.event.event_writer import event_pipe_writer
from apix.core.graph import END, START, Command, GraphManager


pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(autouse=True, scope="module", loop_scope="module")
async def stop_event_loop_after_module():
    """Stop the shared event worker after this module's tests finish."""
    yield
    await apix_event_loop.stop()
    await event_pipe_writer.clear()


async def test_start_node_routes_to_configured_node():
    """START activates the node linked from its direct edge."""
    calls = []

    def first(state):
        calls.append(state)
        return {}

    graph = GraphManager().add_node(first).add_edge(START, "first").compile_graph()

    await graph.invoke_graph({"value": 1})

    assert calls == [{"value": 1}]


async def test_node_update_is_carried_to_end():
    """A node's Command.update is returned from the END event."""
    def increment(state):
        return Command(update={"number": state["number"] + 1})

    graph = (
        GraphManager()
        .add_node(increment)
        .add_edge(START, "increment")
        .add_edge("increment", END)
        .compile_graph()
    )

    assert await graph.invoke_graph({"number": 1}) == {"number": 2}


async def test_node_without_outgoing_edge_routes_to_end():
    """A node with no explicit transition finishes at END."""
    graph = (
        GraphManager()
        .add_node(lambda state: {"finished": True}, "final")
        .add_edge(START, "final")
        .compile_graph()
    )

    assert await graph.invoke_graph({}) == {"finished": True}


async def test_condition_true_routes_to_edge_target():
    """A true condition routes through its generated condition node."""
    calls = []

    def source(state):
        calls.append("source")
        return {"number": 2}

    def target(state):
        calls.append("target")
        return {"matched": True}

    graph = (
        GraphManager()
        .add_node(source)
        .add_node(target)
        .add_edge(START, "source")
        .add_edge("source", "target", lambda state: state["number"] == 2)
        .compile_graph()
    )

    assert await graph.invoke_graph({}) == {"number": 2, "matched": True}
    assert calls == ["source", "target"]


async def test_router_routes_to_selected_target():
    """A router's selected node name is used as Command.goto."""
    def source(state):
        return {"route": "right"}

    def left(state):
        return {"result": "left"}

    def right(state):
        return {"result": "right"}

    graph = (
        GraphManager()
        .add_nodes([source, left, right])
        .add_edge(START, "source")
        .add_router("source", ["left", "right"], lambda state: state["route"])
        .compile_graph()
    )

    assert await graph.invoke_graph({}) == {"route": "right", "result": "right"}


async def test_concurrent_invocations_keep_context_state_isolated():
    """Concurrent calls carry independent state through their event contexts."""
    def increment(state):
        return {"number": state["number"] + 1}

    graph = (
        GraphManager()
        .add_node(increment)
        .add_edge(START, "increment")
        .add_edge("increment", END)
        .compile_graph()
    )

    results = await asyncio.gather(
        graph.invoke_graph({"number": 1}),
        graph.invoke_graph({"number": 10}),
    )

    assert results == [{"number": 2}, {"number": 11}]


async def test_concurrent_invocations_keep_context_state_deep_isolated():
    """Concurrent calls carry independent state through their event contexts."""
    def deep_increment(state):
        return {"number_wrapper": {"number": state["number_wrapper"]["number"] + 1}}

    graph = (
        GraphManager()
        .add_node(deep_increment)
        .add_edge(START, "deep_increment")
        .add_edge("deep_increment", END)
        .compile_graph()
    )

    results = await asyncio.gather(
        graph.invoke_graph({"number_wrapper": {"number": 1}}),
        graph.invoke_graph({"number_wrapper": {"number": 10}}),
    )

    assert results == [{"number_wrapper": {"number": 2}}, {"number_wrapper": {"number": 11}}]
