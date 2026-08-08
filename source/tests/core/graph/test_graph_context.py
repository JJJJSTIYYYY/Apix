"""Focused tests for graph context state, lifecycle, and recovery."""

import asyncio
from dataclasses import is_dataclass
from typing import Annotated, TypedDict

import pytest

from apix.core.graph import AutoMerge, KeepRef
from apix.core.graph.base import START
from apix.core.graph.context import GraphContext
from apix.core.graph.stream import noop_stream_writer


class ContextState(TypedDict):
    values: Annotated[list[int], AutoMerge()]
    resource: Annotated[object, KeepRef()]


def _bind(
    context: GraphContext,
    run_id: str,
    state: dict | None = None,
    *,
    owner_id: str = "graph",
) -> asyncio.Future:
    """Bind a context with the same runtime dependencies as NodeGraph."""
    completion = asyncio.get_running_loop().create_future()
    context._bind(
        owner_id=owner_id,
        run_id=run_id,
        state=state if state is not None else {"value": run_id},
        completion=completion,
        stream_writer=noop_stream_writer(),
    )
    return completion


def test_graph_context_is_a_slots_dataclass():
    """The former TypedDict and store wrapper are represented by one class."""
    context = GraphContext()

    assert is_dataclass(context)
    assert not hasattr(context, "__dict__")
    assert not hasattr(context, "graph_context")
    assert not hasattr(context, "_state_snapshotter")


def test_context_owns_schema_derived_state_behavior():
    """Schema and marker keys belong to each invocation context."""
    context = GraphContext(ContextState)

    assert context._state_schema is ContextState
    assert context._auto_increase_keys == frozenset({"values"})
    assert context._keep_ref_keys == frozenset({"resource"})


def test_new_context_is_pending_and_unbound():
    """A new context begins at START without an invocation attempt."""
    context = GraphContext()

    assert context.status == "pending"
    assert context.run_id is None
    assert context.state == {}
    assert context.node_name == START
    assert context.steps == 0
    assert context.completion is None
    assert context.stream_writer is None
    assert context.is_consumed is False
    assert context.is_bound is False
    assert context.is_active is False


@pytest.mark.asyncio
async def test_bind_transitions_pending_to_running():
    """Binding initializes one running attempt and its first snapshot."""
    context = GraphContext()
    state = {"value": 1}
    completion = _bind(context, "run-1", state)

    assert context.status == "running"
    assert context.run_id == "run-1"
    assert context.state == state
    assert context.state is not state
    assert context.node_name == START
    assert context.completion is completion
    assert context.is_consumed is True
    assert context.is_bound is True
    assert context.is_active is True


def test_pending_context_can_be_aborted_and_resumed():
    """The pending -> aborted -> pending transition needs no runtime future."""
    context = GraphContext()

    context.abort()
    assert context.status == "aborted"

    asyncio.run(context.resume())
    assert context.status == "pending"


def test_pending_context_can_fail_and_resume():
    """The pending -> failed -> pending transition supports setup retries."""
    context = GraphContext()

    context._fail(RuntimeError("setup failed"))
    assert context.status == "failed"

    asyncio.run(context.resume())
    assert context.status == "pending"


def test_invalid_status_transition_is_rejected():
    """The transition table rejects paths outside the lifecycle contract."""
    context = GraphContext()

    with pytest.raises(RuntimeError, match="pending -> finished"):
        context._transition_to("finished")


@pytest.mark.asyncio
async def test_bind_rejects_stale_in_flight_work():
    """A pending recovery cannot bind until all stale work has drained."""
    context = GraphContext()
    context._event_posted()

    with pytest.raises(RuntimeError, match="previous attempt is active"):
        _bind(context, "run-1")

    context._event_received()


def test_drain_counters_never_become_negative():
    """Duplicate drain notifications leave an already idle context idle."""
    context = GraphContext()

    context._event_received()
    context._node_finished()

    assert context._pending_events == 0
    assert context._running_nodes == 0
    assert context._quiescent.is_set()


@pytest.mark.asyncio
async def test_running_abort_resolves_snapshot_and_is_idempotent():
    """Abort resolves the saved state and enters the aborted state once."""
    context = GraphContext()
    completion = _bind(context, "run-1", {"history": ["saved"]})

    context.abort()
    context.abort()

    result = await completion
    assert result == {"history": ["saved"]}
    assert result is not context.state
    assert result["history"] is not context.state["history"]
    assert context.status == "aborted"
    assert context.is_active is False


@pytest.mark.asyncio
async def test_finish_is_idempotent_and_ignores_non_running_contexts():
    """Late and duplicate finish signals cannot alter lifecycle state."""
    pending = GraphContext()
    pending._finish()
    assert pending.status == "pending"

    finished = GraphContext()
    completion = _bind(finished, "run-1")
    finished._finish()
    finished._finish()

    assert await completion == {"value": "run-1"}
    assert finished.status == "finished"


def test_fail_is_idempotent():
    """Only the first failure transition is applied."""
    context = GraphContext()

    context._fail(RuntimeError("first"))
    context._fail(RuntimeError("second"))

    assert context.status == "failed"


@pytest.mark.asyncio
async def test_finished_context_cannot_abort():
    """The terminal finished state rejects interruption."""
    context = GraphContext()
    completion = _bind(context, "run-1")
    context._finish()
    await completion

    with pytest.raises(RuntimeError, match="status finished"):
        context.abort()


@pytest.mark.asyncio
async def test_failed_context_can_resume_with_its_checkpoint():
    """Failure retains state, node, steps, schema, and graph ownership."""
    context = GraphContext(ContextState)
    completion = _bind(
        context,
        "run-1",
        {"values": [1], "resource": object()},
    )
    context.node_name = "retry-node"
    context.steps = 3
    error = RuntimeError("failed")

    context._fail(error)

    with pytest.raises(RuntimeError, match="failed"):
        await completion
    assert context.status == "failed"

    await context.resume()

    assert context.status == "pending"
    assert context.node_name == "retry-node"
    assert context.steps == 3
    assert context._state_schema is ContextState
    assert context.run_id is None
    assert context.completion is None


@pytest.mark.asyncio
async def test_running_and_finished_contexts_cannot_resume():
    """Only failed or aborted contexts may transition back to pending."""
    running = GraphContext()
    _bind(running, "running")

    with pytest.raises(RuntimeError, match="Only failed or aborted"):
        await running.resume()

    finished = GraphContext()
    completion = _bind(finished, "finished")
    finished._finish()
    await completion

    with pytest.raises(RuntimeError, match="Only failed or aborted"):
        await finished.resume()


@pytest.mark.asyncio
async def test_context_cannot_start_while_running_or_after_finish():
    """Running and terminal contexts reject another invocation bind."""
    context = GraphContext()
    _bind(context, "run-1")

    with pytest.raises(RuntimeError, match="must be pending"):
        _bind(context, "run-2")

    context._finish()
    with pytest.raises(RuntimeError, match="must be pending"):
        _bind(context, "run-3")


@pytest.mark.asyncio
async def test_recovered_context_must_use_its_original_graph():
    """A node checkpoint cannot be resumed against another graph topology."""
    context = GraphContext()
    _bind(context, "run-1", owner_id="first-graph")
    context.abort()
    await context.resume()

    with pytest.raises(ValueError, match="original graph"):
        _bind(context, "run-2", owner_id="second-graph")


@pytest.mark.asyncio
async def test_resume_waits_for_queued_events_to_drain():
    """A stale queued event must be consumed before pending can be restored."""
    context = GraphContext()
    _bind(context, "run-1")
    context._event_posted()
    context.abort()

    resume_task = asyncio.create_task(context.resume())
    await asyncio.sleep(0)
    assert not resume_task.done()

    context._event_received()
    await resume_task

    assert context.status == "pending"


@pytest.mark.asyncio
async def test_only_one_concurrent_resume_can_claim_context():
    """Concurrent waiters cannot both transition one context to pending."""
    context = GraphContext()
    _bind(context, "run-1")
    context._event_posted()
    context.abort()

    resume_tasks = [
        asyncio.create_task(context.resume()),
        asyncio.create_task(context.resume()),
    ]
    await asyncio.sleep(0)
    context._event_received()

    results = await asyncio.gather(*resume_tasks, return_exceptions=True)

    assert sum(result is None for result in results) == 1
    [error] = [result for result in results if isinstance(result, RuntimeError)]
    assert "no longer available for recovery" in str(error)
    assert context.status == "pending"
