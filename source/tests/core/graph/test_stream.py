"""Behaviour tests for custom graph stream chunks."""

import asyncio

import pytest
import pytest_asyncio

from apix.core.event.event_loop import apix_event_loop
from apix.core.event.event_writer import event_pipe_writer
from apix.core.graph import START, GraphManager
from apix.core.graph.context import GraphContext
from apix.core.graph.context import get_stream_writer
from apix.core.graph.context.stream_writer import StreamChannel


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(autouse=True, scope="module", loop_scope="session")
async def stop_event_loop_after_module():
    """Stop the shared event worker after this module's tests finish."""
    yield
    await apix_event_loop.stop()
    await event_pipe_writer.clear()


async def _collect(graph, state):
    """Collect one graph stream into a list."""
    return [chunk async for chunk in graph.stream(state)]


async def test_sync_node_emits_chunks_in_write_order():
    """The callable and method writer APIs preserve chunk order."""
    def node(state):
        writer = get_stream_writer()
        writer({"token": "a"})
        writer.write({"token": "b"})
        return {"finished": True}

    graph = GraphManager().add_node(node).add_edge(START, "node").compile_graph()

    assert await _collect(graph, {}) == [{"token": "a"}, {"token": "b"}]


async def test_async_node_can_emit_arbitrary_chunks():
    """Writer context survives awaits and chunks need not be dictionaries."""
    async def node(state):
        writer = get_stream_writer()
        writer("first")
        await asyncio.sleep(0)
        writer("second")
        return {}

    graph = GraphManager().add_node(node).add_edge(START, "node").compile_graph()

    assert await _collect(graph, {}) == ["first", "second"]


async def test_chunks_from_multiple_nodes_share_one_ordered_stream():
    """A run carries the same stream channel across node transitions."""
    def first(state):
        get_stream_writer()(1)
        return {}

    def second(state):
        get_stream_writer()(2)
        return {}

    graph = (
        GraphManager()
        .add_nodes([first, second])
        .add_edge(START, "first")
        .add_edge("first", "second")
        .compile_graph()
    )

    assert await _collect(graph, {}) == [1, 2]


async def test_stream_without_custom_chunks_finishes_cleanly():
    """A graph that writes nothing produces an empty async iteration."""
    graph = (
        GraphManager()
        .add_node(lambda state: {"finished": True}, "node")
        .add_edge(START, "node")
        .compile_graph()
    )

    assert await _collect(graph, {}) == []


async def test_invoke_graph_uses_a_noop_stream_writer():
    """Streaming-aware nodes remain compatible with regular invocation."""
    def node(state):
        get_stream_writer()({"ignored": True})
        return {"finished": True}

    graph = GraphManager().add_node(node).add_edge(START, "node").compile_graph()

    assert await graph.invoke({}) == {"finished": True}


async def test_get_stream_writer_is_unavailable_outside_node_execution():
    """Writer context is reset after each node finishes."""
    with pytest.raises(RuntimeError, match="only available while a graph node"):
        get_stream_writer()


async def test_stream_yields_queued_chunks_before_propagating_node_error():
    """An execution error does not discard chunks already sent by the node."""
    def node(state):
        get_stream_writer()({"status": "started"})
        raise RuntimeError("stream failed")

    graph = GraphManager().add_node(node).add_edge(START, "node").compile_graph()
    stream = graph.stream({})

    assert await anext(stream) == {"status": "started"}
    with pytest.raises(RuntimeError, match="stream failed"):
        await anext(stream)


async def test_stream_yields_queued_chunks_before_node_timeout():
    """A deadline preserves chunks emitted before the node was cancelled."""
    async def node(state):
        get_stream_writer()({"status": "started"})
        await asyncio.sleep(60)

    graph = (
        GraphManager()
        .add_node(node, timeout=0.02)
        .add_edge(START, "node")
        .compile_graph()
    )
    stream = graph.stream({})

    assert await anext(stream) == {"status": "started"}
    with pytest.raises(
        TimeoutError,
        match=r"Graph node `node` timed out after 0.02 seconds",
    ):
        await anext(stream)


async def test_stream_rejects_non_dict_state():
    """Streaming and regular invocation enforce the same input contract."""
    graph = (
        GraphManager()
        .add_node(lambda state: {}, "node")
        .add_edge(START, "node")
        .compile_graph()
    )

    with pytest.raises(TypeError, match="Graph state must be a dict"):
        await anext(graph.stream([]))


async def test_concurrent_streams_keep_writer_channels_isolated():
    """Context-local writers prevent concurrent graph runs from mixing chunks."""
    async def node(state):
        writer = get_stream_writer()
        writer(f"{state['run']}:first")
        await asyncio.sleep(0)
        writer(f"{state['run']}:second")
        return {}

    graph = GraphManager().add_node(node).add_edge(START, "node").compile_graph()

    left, right = await asyncio.gather(
        _collect(graph, {"run": "left"}),
        _collect(graph, {"run": "right"}),
    )

    assert left == ["left:first", "left:second"]
    assert right == ["right:first", "right:second"]


async def test_closing_stream_early_cancels_its_graph_run():
    """Closing the async generator releases its run and registered context."""
    release_node = asyncio.Event()

    async def node(state):
        get_stream_writer()("started")
        await release_node.wait()
        return {}

    graph = GraphManager().add_node(node).add_edge(START, "node").compile_graph()
    context = GraphContext()
    stream = graph.stream({}, context)

    assert await anext(stream) == "started"
    await stream.aclose()

    assert graph._active_runs == set()
    assert context.status == "aborted"
    release_node.set()
    await asyncio.sleep(0)


async def test_completed_context_cannot_be_reused():
    """A GraphContext is consumed by its first invocation."""
    graph = (
        GraphManager()
        .add_node(lambda state: {"finished": True}, "node")
        .add_edge(START, "node")
        .compile_graph()
    )
    context = GraphContext()

    assert await graph.invoke({}, context) == {"finished": True}

    assert context.status == "finished"
    with pytest.raises(RuntimeError, match="must be pending"):
        await graph.invoke({}, context)


async def test_aborted_stream_context_can_resume_with_a_new_writer():
    """Stream recovery waits for stale work and binds a fresh channel."""
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    first_finished = asyncio.Event()
    attempts = 0

    async def node(state):
        nonlocal attempts
        attempts += 1
        writer = get_stream_writer()
        if attempts == 1:
            writer("first:started")
            first_started.set()
            await release_first.wait()
            first_finished.set()
            return {"stale": True}
        writer("resumed:started")
        await asyncio.sleep(0)
        writer("resumed:finished")
        return {"recovered": True}

    graph = GraphManager().add_node(node).add_edge(START, "node").compile_graph()
    context = GraphContext()
    first_stream = graph.stream({"initial": True}, context)

    assert await anext(first_stream) == "first:started"
    await first_started.wait()
    await graph.abort(context)
    with pytest.raises(StopAsyncIteration):
        await anext(first_stream)

    resume_task = asyncio.create_task(context.resume())
    await asyncio.sleep(0)
    assert not resume_task.done()

    release_first.set()
    await first_finished.wait()
    await resume_task

    chunks = [
        chunk
        async for chunk in graph.stream(context.state, context)
    ]

    assert chunks == ["resumed:started", "resumed:finished"]
    assert context.state == {"initial": True, "recovered": True}
    assert "stale" not in context.state
    assert context.status == "finished"


async def test_stream_channel_close_is_idempotent_and_rejects_late_writes():
    """A closed queue emits one terminator and cannot accept more chunks."""
    channel = StreamChannel()
    channel.close()
    channel.close()

    with pytest.raises(RuntimeError, match="closed graph stream"):
        channel.writer("late")
    with pytest.raises(StopAsyncIteration):
        await anext(channel)
