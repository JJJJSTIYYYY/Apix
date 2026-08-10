"""Breakpoint and external-resume tests for graph interruption."""

import asyncio
import time

import pytest
import pytest_asyncio

from apix.core.event import (
    ApixEvent,
    EventType,
    apix_event_loop,
    apix_event_registry,
    event_pipe_writer,
)
from apix.core.graph import START, GraphManager
from apix.core.graph.context import GraphContext, apix_graph_context
from apix.core.graph.interrupter import Block, interrupt, interrupted_hook


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(autouse=True, scope="module", loop_scope="session")
async def stop_event_loop_after_module():
    """Leave the process-global event worker clean for later test modules."""
    yield
    await apix_event_loop.stop()
    await event_pipe_writer.clear()


def _block(*, data=None) -> Block:
    """Create one block on the currently running test loop."""
    return Block(
        run_id="graph-run",
        block_id="block-id",
        namespace="unit",
        with_data=data,
        _future=asyncio.get_running_loop().create_future(),
    )


async def test_block_resolves_once_and_exposes_completion_state():
    """The first external answer wins and duplicate answers are harmless."""
    block = _block(data={"question": "continue?"})

    async def wait_for_block():
        return await block

    waiter = asyncio.create_task(wait_for_block())
    await asyncio.sleep(0)

    assert block.done is False
    assert block.cancelled is False

    block.resolve("yes")
    block.resolve("ignored")
    block.cancel()

    assert await waiter == "yes"
    assert block.done is True
    assert block.cancelled is False


async def test_block_rejects_an_invalid_future():
    """A malformed public Block fails immediately instead of on first await."""
    with pytest.raises(TypeError, match="must be an asyncio.Future"):
        Block(
            run_id="graph-run",
            block_id="block-id",
            namespace="unit",
            with_data=None,
            _future=None,  # type: ignore[arg-type]
        )


async def test_interrupt_requires_an_active_graph_node_context():
    """A breakpoint cannot be created outside an active node invocation."""
    with pytest.raises(RuntimeError, match="only available while a graph is invoked"):
        await interrupt()

    with apix_graph_context(GraphContext()):
        with pytest.raises(RuntimeError, match="active graph node"):
            await interrupt()


async def test_interrupted_hook_rejects_non_block_event_context():
    """The public hook boundary validates the event transport payload."""
    received = []

    async def invalid_context_hook(block: Block) -> None:
        received.append(block)

    decorated = interrupted_hook()(invalid_context_hook)
    assert decorated is invalid_context_hook

    try:
        [handler] = apix_event_registry.get_handlers("graph__interrupted")
        event = ApixEvent(
            event_id="event-id",
            event_type=EventType.WORKFLOW,
            event_name="graph__interrupted",
            context={},
            timestamp=time.time(),
        )

        with pytest.raises(TypeError, match="must carry a Block"):
            await handler.callback(event)
        assert received == []
    finally:
        apix_event_registry.unsubscribe(invalid_context_hook.__name__)


async def test_graph_pauses_and_resumes_at_multiple_breakpoints():
    """One node may pause repeatedly without mixing block identity or input."""
    blocks: asyncio.Queue[Block] = asyncio.Queue()

    async def review(state):
        first = await interrupt(data={"step": 1})
        second = await interrupt(data={"step": 2, "first": first})
        return {"answers": [first, second]}

    graph = (
        GraphManager()
        .add_node(review)
        .add_edge(START, "review")
        .compile_graph(using_namespace="review-flow")
    )

    @graph.add_interrupted_hook
    async def capture_review_block(block: Block) -> None:
        await blocks.put(block)

    context = GraphContext()
    invocation = asyncio.create_task(graph.invoke({}, context))

    first = await asyncio.wait_for(blocks.get(), timeout=1)
    assert invocation.done() is False
    assert first.run_id == context.run_id
    assert first.namespace == "review-flow"
    assert first.with_data == {"step": 1}
    first.resolve("approved")

    second = await asyncio.wait_for(blocks.get(), timeout=1)
    assert invocation.done() is False
    assert second.run_id == first.run_id
    assert second.block_id != first.block_id
    assert second.with_data == {"step": 2, "first": "approved"}
    second.resolve({"edited": True})

    assert await asyncio.wait_for(invocation, timeout=1) == {
        "answers": ["approved", {"edited": True}],
    }

    assert capture_review_block.__name__ in (
        apix_event_registry.get_all_handlers_meta()
    )
    graph.decompose()
    assert capture_review_block.__name__ not in (
        apix_event_registry.get_all_handlers_meta()
    )

    with pytest.raises(RuntimeError, match="decomposed NodeGraph"):
        graph.add_interrupted_hook(capture_review_block)


async def test_external_block_cancel_aborts_graph_at_saved_snapshot():
    """Cancelling a breakpoint stops its node and all downstream routing."""
    blocks: asyncio.Queue[Block] = asyncio.Queue()
    continued = asyncio.Event()
    downstream_called = asyncio.Event()

    def prepare(state):
        return {"checkpoint": "prepared"}

    async def wait_for_decision(state):
        await interrupt(data="optional")
        continued.set()
        return {"decision": "continued"}

    def downstream(state):
        downstream_called.set()
        return {"downstream": True}

    graph = (
        GraphManager()
        .add_nodes([prepare, wait_for_decision, downstream])
        .add_edge(START, "prepare")
        .add_edge("prepare", "wait_for_decision")
        .add_edge("wait_for_decision", "downstream")
        .compile_graph(using_namespace="cancel-flow")
    )

    @graph.add_interrupted_hook
    async def capture_cancelled_block(block: Block) -> None:
        await blocks.put(block)

    context = GraphContext()
    invocation = asyncio.create_task(
        graph.invoke({"initial": True}, context)
    )
    block = await asyncio.wait_for(blocks.get(), timeout=1)
    block.cancel()

    assert await asyncio.wait_for(invocation, timeout=1) == {
        "initial": True,
        "checkpoint": "prepared",
    }
    await asyncio.sleep(0)

    assert block.done is True
    assert block.cancelled is True
    assert context.status == "aborted"
    assert context.node_name == "wait_for_decision"
    assert continued.is_set() is False
    assert downstream_called.is_set() is False


async def test_interrupt_timeout_resumes_graph_and_cancels_block():
    """A breakpoint deadline resumes with None and closes late resolution."""
    blocks: asyncio.Queue[Block] = asyncio.Queue()

    async def wait_briefly(state):
        return {"answer": await interrupt(data="timed", timeout=0.01)}

    graph = (
        GraphManager()
        .add_node(wait_briefly)
        .add_edge(START, "wait_briefly")
        .compile_graph(using_namespace="timeout-flow")
    )

    @graph.add_interrupted_hook
    async def capture_timed_block(block: Block) -> None:
        await blocks.put(block)

    invocation = asyncio.create_task(graph.invoke({}))
    block = await asyncio.wait_for(blocks.get(), timeout=1)

    assert await asyncio.wait_for(invocation, timeout=1) == {"answer": None}
    assert block.cancelled is True
    block.resolve("too late")


async def test_node_timeout_is_not_swallowed_by_interrupt_cancellation():
    """Runtime cancellation remains distinct from external Block.cancel()."""
    blocks: asyncio.Queue[Block] = asyncio.Queue()

    async def wait_forever(state):
        await interrupt(data="timed node")
        return {}

    graph = (
        GraphManager()
        .add_node(wait_forever, timeout=0.02)
        .add_edge(START, "wait_forever")
        .compile_graph(using_namespace="node-timeout-flow")
    )

    @graph.add_interrupted_hook
    async def capture_node_timeout_block(block: Block) -> None:
        await blocks.put(block)

    invocation = asyncio.create_task(graph.invoke({}))
    block = await asyncio.wait_for(blocks.get(), timeout=1)

    with pytest.raises(
        TimeoutError,
        match=r"Graph node `wait_forever` timed out after 0.02 seconds",
    ):
        await asyncio.wait_for(invocation, timeout=1)
    assert block.cancelled is True
