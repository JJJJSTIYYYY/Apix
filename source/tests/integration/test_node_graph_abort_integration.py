"""Integration tests for aborting event-driven graph invocations."""

import asyncio
from typing import Annotated, TypedDict

import pytest
import pytest_asyncio

from apix.core.event.event_loop import apix_event_loop
from apix.core.event.event_writer import event_pipe_writer
from apix.core.graph import AutoMerge, END, START, GraphManager
from apix.core.graph.context import GraphContext
from apix.core.graph.context import get_stream_writer


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
    yield
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
    context = GraphContext()
    invocation = asyncio.create_task(
        graph.invoke({"history": ["initial"]}, context)
    )

    await asyncio.wait_for(slow_started.wait(), timeout=1)
    await graph.abort(context)
    result = await asyncio.wait_for(invocation, timeout=0.5)

    assert result == {
        "history": ["initial", "prepare"],
        "route": "slow",
    }
    assert not slow_finished.is_set()
    assert not final_called.is_set()
    assert graph._active_runs == set()

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


async def test_context_abort_directly_finishes_its_invocation():
    """The caller-owned context is itself a usable cooperative abort handle."""
    slow_started = asyncio.Event()
    release_slow = asyncio.Event()
    slow_finished = asyncio.Event()

    async def slow(state):
        slow_started.set()
        await release_slow.wait()
        slow_finished.set()
        return {"history": ["slow"]}

    graph = (
        GraphManager(AbortState)
        .add_node(slow)
        .add_edge(START, "slow")
        .compile_graph()
    )
    context = GraphContext()
    invocation = asyncio.create_task(
        graph.invoke({"history": ["initial"]}, context)
    )

    await asyncio.wait_for(slow_started.wait(), timeout=1)
    context.abort()
    result = await asyncio.wait_for(invocation, timeout=0.5)

    assert result == {"history": ["initial"]}
    assert graph._active_runs == set()
    assert not slow_finished.is_set()

    release_slow.set()
    await asyncio.wait_for(slow_finished.wait(), timeout=1)
    await asyncio.sleep(0.02)
    assert result == {"history": ["initial"]}


async def test_aborted_context_waits_for_stale_node_then_resumes_checkpoint():
    """Recovery retries the interrupted node without committing its stale result."""
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    first_finished = asyncio.Event()
    attempts = 0

    async def recoverable(state):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            first_started.set()
            await release_first.wait()
            first_finished.set()
            return {"history": ["stale-result"]}
        return {"history": ["recovered-result"]}

    graph = (
        GraphManager(AbortState)
        .add_node(recoverable)
        .add_edge(START, "recoverable")
        .compile_graph()
    )
    context = GraphContext()
    invocation = asyncio.create_task(
        graph.invoke({"history": ["initial"]}, context)
    )

    await asyncio.wait_for(first_started.wait(), timeout=1)
    await graph.abort(context)
    assert await asyncio.wait_for(invocation, timeout=0.5) == {
        "history": ["initial"]
    }
    assert context.status == "aborted"
    assert context.node_name == "recoverable"

    resume_task = asyncio.create_task(context.resume())
    await asyncio.sleep(0)
    assert not resume_task.done()

    release_first.set()
    await asyncio.wait_for(first_finished.wait(), timeout=1)
    await asyncio.wait_for(resume_task, timeout=1)
    assert context.status == "pending"

    result = await graph.invoke(context.state, context)

    assert result == {
        "history": ["initial", "recovered-result"],
    }
    assert "stale-result" not in result["history"]
    assert attempts == 2
    assert context.status == "finished"
    assert context.node_name == END
    assert context.steps == 1


async def test_failed_context_resumes_at_failed_node():
    """A failed node is retried from its pre-execution state snapshot."""
    attempts = 0

    async def flaky(state):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("first attempt failed")
        return {"history": ["recovered"]}

    graph = (
        GraphManager(AbortState)
        .add_node(flaky)
        .add_edge(START, "flaky")
        .compile_graph()
    )
    context = GraphContext()

    with pytest.raises(RuntimeError, match="first attempt failed"):
        await graph.invoke({"history": ["initial"]}, context)

    assert context.status == "failed"
    assert context.node_name == "flaky"
    assert context.state == {"history": ["initial"]}

    await context.resume()
    result = await graph.invoke(context.state, context)

    assert result == {"history": ["initial", "recovered"]}
    assert attempts == 2
    assert context.status == "finished"


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
    context = GraphContext()
    stream = graph.stream({"history": ["initial"]}, context)

    chunks = [
        await asyncio.wait_for(anext(stream), timeout=1)
        for _ in range(3)
    ]
    await asyncio.wait_for(slow_started.wait(), timeout=1)
    await graph.abort(context)

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=0.5)

    assert chunks == ["prepare:started", "prepare:finished", "slow:started"]
    assert not slow_finished.is_set()
    assert not final_called.is_set()
    assert graph._active_runs == set()

    release_slow.set()
    await asyncio.wait_for(slow_finished.wait(), timeout=1)
    await asyncio.sleep(0.02)
    assert not final_called.is_set()
