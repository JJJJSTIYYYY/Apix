"""Integration tests for aborting event-driven graph invocations."""

import asyncio
from typing import Annotated, TypedDict

import pytest
import pytest_asyncio

from apix.core.event.event_loop import apix_event_loop
from apix.core.event.event_writer import event_pipe_writer
from apix.core.graph import AutoMerge, END, START, GraphManager
from apix.core.graph.context import GraphContextStore
from apix.core.graph.context.context_store_manager import (
    _context_store_manager,
)
from apix.core.graph.stream import get_stream_writer


pytestmark = pytest.mark.asyncio(loop_scope="session")


class AbortState(TypedDict, total=False):
    """State shared by the multi-stage abort integration graphs."""

    history: Annotated[list[str], AutoMerge()]
    route: str
    slow_result: str
    final_result: str


@pytest_asyncio.fixture(autouse=True, scope="module", loop_scope="session")
async def clean_graph_runtime_after_module():
    """Leave the shared event runtime clean for other integration modules."""
    _context_store_manager.clear_stores()
    yield
    _context_store_manager.clear_stores()
    await apix_event_loop.stop()
    await event_pipe_writer.clear()


async def test_abort_invoke_returns_last_completed_snapshot_and_stops_routing():
    """Non-streaming abort skips the current update and all downstream nodes."""
    slow_started = asyncio.Event()
    release_slow = asyncio.Event()
    slow_finished = asyncio.Event()
    final_called = asyncio.Event()

    def prepare(state):
        return {"history": ["prepare"], "route": "slow"}

    async def slow(state):
        slow_started.set()
        await release_slow.wait()
        slow_finished.set()
        return {"history": ["slow"], "slow_result": "completed"}

    def unused(state):
        return {"history": ["unused"]}

    def final(state):
        final_called.set()
        return {"history": ["final"], "final_result": "completed"}

    graph = (
        GraphManager(AbortState)
        .add_nodes([prepare, slow, unused, final])
        .add_edge(START, "prepare")
        .add_router(
            "prepare",
            ["slow", "unused"],
            lambda state: state["route"],
        )
        .add_edge("slow", "final")
        .add_edge("unused", "final")
        .add_edge("final", END)
        .compile_graph()
    )
    store = GraphContextStore("invoke-abort")
    invocation = asyncio.create_task(
        graph.invoke({"history": ["initial"]}, store)
    )

    await asyncio.wait_for(slow_started.wait(), timeout=1)
    await graph.abort(store.get_store_id())
    result = await asyncio.wait_for(invocation, timeout=0.5)

    assert result == {
        "history": ["initial", "prepare"],
        "route": "slow",
    }
    assert not slow_finished.is_set()
    assert not final_called.is_set()
    assert graph._active_runs == set()
    assert _context_store_manager.get_store(store.get_store_id()) is None

    # Abort is cooperative: the running node is allowed to finish, but its
    # result cannot reactivate routing or mutate the returned checkpoint.
    release_slow.set()
    await asyncio.wait_for(slow_finished.wait(), timeout=1)
    await asyncio.sleep(0.02)
    assert not final_called.is_set()
    assert result == {
        "history": ["initial", "prepare"],
        "route": "slow",
    }


async def test_abort_stream_flushes_chunks_then_stops_complex_graph():
    """Streaming abort preserves queued output and prevents later nodes."""
    slow_started = asyncio.Event()
    release_slow = asyncio.Event()
    slow_finished = asyncio.Event()
    final_called = asyncio.Event()

    async def prepare(state):
        writer = get_stream_writer()
        writer("prepare:started")
        await asyncio.sleep(0)
        writer("prepare:finished")
        return {"history": ["prepare"], "route": "slow"}

    async def slow(state):
        get_stream_writer()("slow:started")
        slow_started.set()
        await release_slow.wait()
        slow_finished.set()
        return {"history": ["slow"], "slow_result": "completed"}

    def unused(state):
        get_stream_writer()("unused")
        return {"history": ["unused"]}

    def final(state):
        final_called.set()
        get_stream_writer()("final")
        return {"history": ["final"], "final_result": "completed"}

    graph = (
        GraphManager(AbortState)
        .add_nodes([prepare, slow, unused, final])
        .add_edge(START, "prepare")
        .add_router(
            "prepare",
            ["slow", "unused"],
            lambda state: state["route"],
        )
        .add_edge("slow", "final")
        .add_edge("unused", "final")
        .compile_graph()
    )
    store = GraphContextStore("stream-abort")
    stream = graph.stream({"history": ["initial"]}, store)

    chunks = [
        await asyncio.wait_for(anext(stream), timeout=1)
        for _ in range(3)
    ]
    await asyncio.wait_for(slow_started.wait(), timeout=1)
    await graph.abort(store.get_store_id())

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=0.5)

    assert chunks == ["prepare:started", "prepare:finished", "slow:started"]
    assert not slow_finished.is_set()
    assert not final_called.is_set()
    assert graph._active_runs == set()
    assert _context_store_manager.get_store(store.get_store_id()) is None

    release_slow.set()
    await asyncio.wait_for(slow_finished.wait(), timeout=1)
    await asyncio.sleep(0.02)
    assert not final_called.is_set()
