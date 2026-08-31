"""Focused tests for graph context state, lifecycle, and snapshots."""

import asyncio
import json
from dataclasses import is_dataclass
import time
from typing import Annotated, TypedDict

import pytest

from apix.core.graph import AutoMerge, KeepRef
from apix.core.graph.base import START
from apix.core.graph.context import GraphContext, GraphContextSnapshot
from apix.core.graph.context import noop_stream_writer


class ContextState(TypedDict):
    values: Annotated[list[int], AutoMerge()]
    resource: Annotated[dict, KeepRef()]


def _bind(
    context: GraphContext,
    run_id: str,
    state: dict | None = None,
    *,
    context_namespace: str = "graph",
) -> asyncio.Future:
    """Bind a context with the same runtime dependencies as NodeGraph."""
    completion = asyncio.get_running_loop().create_future()
    context._bind(
        context_namespace=context_namespace,
        run_id=run_id,
        state=state if state is not None else {"value": run_id},
        completion=completion,
        stream_writer=noop_stream_writer(),
    )
    return completion


def test_graph_context_is_a_slots_dataclass_without_old_recovery_barrier():
    """The context is one class and no longer owns quiescence bookkeeping."""
    context = GraphContext()

    assert is_dataclass(context)
    assert not hasattr(context, "__dict__")
    assert not hasattr(context, "graph_context")
    assert not hasattr(context, "_state_snapshotter")
    assert not hasattr(context, "_has_snapshot")
    assert not hasattr(context, "_pending_events")
    assert not hasattr(context, "_running_nodes")
    assert not hasattr(context, "_quiescent")
    assert not hasattr(context, "resume")


def test_context_owns_schema_derived_state_behavior():
    """Schema and marker keys belong to each invocation context."""
    context = GraphContext(ContextState)

    assert context._state_schema is ContextState
    assert context._auto_merge_keys == frozenset({"values"})
    assert context._keep_ref_keys == frozenset({"resource"})


def test_new_context_is_pending_unbound_and_has_no_snapshot():
    """A new context begins at START without runtime or recovery state."""
    context = GraphContext()

    assert context.status == "pending"
    assert context.run_id is None
    assert context.state == {}
    assert context.target_node_name == START
    assert context.steps == 0
    assert context.context_snapshot == []
    assert context.completion is None
    assert context.stream_writer is None
    assert context.is_consumed is False
    assert context.is_bound is False
    assert context.is_active is False


@pytest.mark.asyncio
async def test_bind_transitions_pending_to_running_without_taking_snapshot():
    """START binding initializes runtime fields but leaves the snapshot absent."""
    context = GraphContext()
    state = {"value": 1}
    completion = _bind(context, "run-1", state)

    assert context.status == "running"
    assert context.run_id == "run-1"
    assert context.state == state
    assert context.state is not state
    assert context.target_node_name == START
    assert context.context_snapshot == []
    assert context.completion is completion
    assert context.is_consumed is True
    assert context.is_bound is True
    assert context.is_active is True


def test_snapshot_requires_an_active_bound_context():
    """Detached and completed contexts cannot manufacture checkpoints."""
    context = GraphContext()

    with pytest.raises(RuntimeError, match="only be taken from an active"):
        context.take_a_snapshot()


@pytest.mark.asyncio
async def test_take_a_snapshot_deep_copies_recoverable_state():
    """Later live-state mutations cannot alter the saved checkpoint."""
    context = GraphContext()
    _bind(context, "run-1", {"nested": [1]}, context_namespace="agent")
    context.target_node_name = "retry"
    context.steps = 2

    before_snapshot = time.time()
    context.take_a_snapshot()
    after_snapshot = time.time()

    assert len(context.context_snapshot) == 1
    snapshot = context.context_snapshot[-1]
    assert before_snapshot <= snapshot["timestamp"] <= after_snapshot
    assert {
        key: value
        for key, value in snapshot.items()
        if key != "timestamp"
    } == {
        "state": {"nested": [1]},
        "target_node_name": "retry",
        "steps": 2,
        "namespace": "agent",
    }
    assert snapshot["state"] is not context.state
    assert snapshot["state"]["nested"] is not context.state["nested"]

    context.state["nested"].append(2)
    context.state["new"] = "live-only"

    assert snapshot["state"] == {"nested": [1]}
    assert "run_id" not in snapshot
    assert "completion" not in snapshot
    assert "stream_writer" not in snapshot
    assert json.loads(json.dumps(snapshot)) == snapshot


@pytest.mark.asyncio
async def test_from_snapshot_deep_copies_every_field_including_keep_ref():
    """Recovery deliberately ignores KeepRef and isolates the new attempt."""
    resource = {"items": [1]}
    context = GraphContext(ContextState)
    _bind(
        context,
        "run-1",
        {"values": [1], "resource": resource},
        context_namespace="agent",
    )
    context.target_node_name = "retry"
    context.steps = 3
    context.take_a_snapshot()
    snapshot_history = context.context_snapshot
    snapshot = snapshot_history[-1]
    assert snapshot["state"] is not context.state
    assert snapshot["state"]["values"] is not context.state["values"]
    assert snapshot["state"]["resource"] is not resource
    assert snapshot["state"]["resource"]["items"] is not resource["items"]

    recovered = GraphContext.from_snapshot(snapshot, ContextState)

    assert recovered.status == "pending"
    assert recovered.run_id is None
    assert recovered.completion is None
    assert recovered.stream_writer is None
    assert recovered.is_consumed is False
    assert recovered.target_node_name == "retry"
    assert recovered.steps == 3
    assert recovered._context_namespace == "agent"
    assert recovered._state_schema is ContextState
    assert recovered.context_snapshot is not snapshot_history
    assert len(recovered.context_snapshot) == 1
    assert recovered.context_snapshot[-1] is not snapshot
    assert recovered.state is recovered.context_snapshot[-1]["state"]
    assert recovered.state is not snapshot["state"]
    assert recovered.state["values"] is not snapshot["state"]["values"]
    assert recovered.state["resource"] is not snapshot["state"]["resource"]
    assert recovered.state["resource"] is not resource
    assert recovered.state["resource"]["items"] is not resource["items"]


@pytest.mark.parametrize("snapshot", [None])
def test_from_snapshot_rejects_missing_snapshot(snapshot):
    """START failures without a checkpoint cannot be recovered."""
    with pytest.raises(RuntimeError, match="without a snapshot"):
        GraphContext.from_snapshot(snapshot)


def test_from_snapshot_rejects_invalid_container():
    """The public restoration API validates its container contract."""
    with pytest.raises(TypeError, match="dict or a list of dicts"):
        GraphContext.from_snapshot(())


def test_from_snapshot_rejects_empty_history():
    """An empty history contains no recoverable checkpoint."""
    with pytest.raises(RuntimeError, match="without a snapshot"):
        GraphContext.from_snapshot([])


def test_from_snapshot_rejects_missing_fields():
    """Partially persisted checkpoints fail with a useful field list."""
    with pytest.raises(ValueError, match="missing required fields: namespace, steps"):
        GraphContext.from_snapshot({"state": {}, "target_node_name": "node"})


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("state", [], "state must be a dict"),
        ("target_node_name", 1, "target_node_name must be a string"),
        ("steps", True, "steps must be an int"),
        ("steps", 1.5, "steps must be an int"),
        ("namespace", None, "namespace must be a string"),
    ],
)
def test_from_snapshot_rejects_invalid_field_types(key, value, message):
    """Stored fields retain explicit runtime contracts."""
    snapshot: GraphContextSnapshot = {
        "state": {},
        "target_node_name": "node",
        "steps": 0,
        "namespace": "agent",
    }
    snapshot[key] = value

    with pytest.raises(TypeError, match=message):
        GraphContext.from_snapshot(snapshot)


def test_from_snapshot_rejects_negative_steps():
    """A checkpoint cannot precede the start of graph execution."""
    snapshot: GraphContextSnapshot = {
        "state": {},
        "target_node_name": "node",
        "steps": -1,
        "namespace": "agent",
    }

    with pytest.raises(ValueError, match="cannot be negative"):
        GraphContext.from_snapshot(snapshot)


@pytest.mark.asyncio
async def test_snapshot_history_restores_latest_version_by_default():
    """Each checkpoint is retained and default recovery selects the latest."""
    context = GraphContext()
    _bind(context, "run-1", {"history": ["first"]}, context_namespace="agent")
    context.target_node_name = "first-node"
    context.steps = 1
    context.take_a_snapshot()

    context.state = {"history": ["second"]}
    context.target_node_name = "second-node"
    context.steps = 2
    context.take_a_snapshot()

    recovered = GraphContext.from_snapshot(context.context_snapshot)

    assert len(context.context_snapshot) == 2
    assert recovered.state == {"history": ["second"]}
    assert recovered.target_node_name == "second-node"
    assert recovered.steps == 2
    assert len(recovered.context_snapshot) == 2
    assert recovered.context_snapshot is not context.context_snapshot
    assert recovered.context_snapshot[-1] is not context.context_snapshot[-1]


@pytest.mark.asyncio
async def test_snapshot_history_restores_selected_version_as_new_branch():
    """Restoring an older checkpoint drops later versions from the new branch."""
    context = GraphContext()
    _bind(context, "run-1", {"value": 1}, context_namespace="agent")

    for version in range(3):
        context.state = {"value": version}
        context.target_node_name = f"node-{version}"
        context.steps = version
        context.take_a_snapshot()

    recovered = GraphContext.from_snapshot(context.context_snapshot, version=1)
    recovered_with_negative_version = GraphContext.from_snapshot(
        context.context_snapshot,
        version=-2,
    )

    assert recovered.state == {"value": 1}
    assert recovered.target_node_name == "node-1"
    assert recovered.steps == 1
    assert len(recovered.context_snapshot) == 2
    assert recovered.get_snapshot() == context.context_snapshot[1]
    assert recovered.get_snapshot(0) == context.context_snapshot[0]
    assert recovered_with_negative_version.state == recovered.state
    assert recovered_with_negative_version.context_snapshot == (
        recovered.context_snapshot
    )


@pytest.mark.parametrize("version", [3, -4])
def test_from_snapshot_rejects_missing_version(version):
    """Versions outside the stored history fail explicitly."""
    snapshot: GraphContextSnapshot = {
        "state": {},
        "target_node_name": "node",
        "steps": 0,
        "namespace": "agent",
    }

    with pytest.raises(IndexError, match="list index out of range"):
        GraphContext.from_snapshot([snapshot, snapshot, snapshot], version=version)


@pytest.mark.parametrize("version", [1.5, "1"])
def test_from_snapshot_uses_native_list_index_validation(version):
    """History version validation follows normal list indexing semantics."""
    snapshot: GraphContextSnapshot = {
        "state": {},
        "target_node_name": "node",
        "steps": 0,
        "namespace": "agent",
    }

    with pytest.raises(TypeError, match="list indices must be integers"):
        GraphContext.from_snapshot([snapshot], version=version)


def test_invalid_status_transition_is_rejected():
    """The transition table rejects paths outside the lifecycle contract."""
    context = GraphContext()

    with pytest.raises(RuntimeError, match="pending -> finished"):
        context._transition_to("finished")


def test_pending_context_can_abort_or_fail_but_has_no_recovery_snapshot():
    """Setup failures stay terminal because no ordinary node was checkpointed."""
    aborted = GraphContext()
    aborted.abort()
    aborted.abort()
    assert aborted.status == "aborted"
    assert aborted.context_snapshot == []

    failed = GraphContext()
    failed._fail(RuntimeError("first"))
    failed._fail(RuntimeError("second"))
    assert failed.status == "failed"
    assert failed.context_snapshot == []


@pytest.mark.asyncio
async def test_running_abort_resolves_the_saved_snapshot_and_is_idempotent():
    """Abort returns the checkpoint even if newer context state is present."""
    context = GraphContext()
    completion = _bind(context, "run-1", {"history": ["saved"]})
    context.target_node_name = "retry"
    context.take_a_snapshot()
    context.state = {"history": ["newer"]}

    context.abort()
    context.abort()

    result = await completion
    assert result == {"history": ["saved"]}
    assert result is not context.context_snapshot[-1]["state"]
    assert result["history"] is not context.context_snapshot[-1]["state"]["history"]
    assert context.status == "aborted"
    assert context.is_active is False


@pytest.mark.asyncio
async def test_finish_is_idempotent_and_does_not_replace_snapshot():
    """END resolves current state while leaving the previous checkpoint intact."""
    pending = GraphContext()
    pending._finish()
    assert pending.status == "pending"

    finished = GraphContext()
    completion = _bind(finished, "run-1")
    finished.target_node_name = "node"
    finished.take_a_snapshot()
    snapshot = finished.context_snapshot
    finished.state = {"value": "finished"}
    finished._finish()
    finished._finish()

    assert await completion == {"value": "finished"}
    assert finished.status == "finished"
    assert finished.context_snapshot is snapshot
    assert finished.context_snapshot[-1]["state"] == {"value": "run-1"}


@pytest.mark.asyncio
async def test_failed_context_restores_into_a_new_pending_context():
    """The original attempt stays failed while its deep copy becomes reusable."""
    context = GraphContext(ContextState)
    completion = _bind(
        context,
        "run-1",
        {"values": [1], "resource": {}},
    )
    context.target_node_name = "retry-node"
    context.steps = 3
    context.take_a_snapshot()
    error = RuntimeError("failed")
    context._fail(error)

    with pytest.raises(RuntimeError, match="failed"):
        await completion
    recovered = GraphContext.from_snapshot(context.context_snapshot)

    assert context.status == "failed"
    assert recovered.status == "pending"
    assert recovered.target_node_name == "retry-node"
    assert recovered.steps == 3
    assert recovered._state_schema is None
    assert recovered.run_id is None
    assert recovered.completion is None


@pytest.mark.asyncio
async def test_finished_context_cannot_abort_or_start_again():
    """Finished contexts remain terminal and single-use."""
    context = GraphContext()
    completion = _bind(context, "run-1")
    context._finish()
    await completion

    with pytest.raises(RuntimeError, match="status finished"):
        context.abort()
    with pytest.raises(RuntimeError, match="must be pending"):
        _bind(context, "run-2")


@pytest.mark.asyncio
async def test_running_context_cannot_start_again():
    """A context cannot represent two invocation attempts."""
    context = GraphContext()
    _bind(context, "run-1")

    with pytest.raises(RuntimeError, match="must be pending"):
        _bind(context, "run-2")


@pytest.mark.asyncio
async def test_recovered_context_must_use_its_original_namespace():
    """A checkpoint may move to a replacement graph, but not another namespace."""
    original = GraphContext()
    _bind(original, "run-1", context_namespace="first-graph")
    original.target_node_name = "retry"
    original.take_a_snapshot()
    original.abort()
    recovered = GraphContext.from_snapshot(original.context_snapshot)

    with pytest.raises(ValueError, match="original namespace"):
        _bind(recovered, "run-2", context_namespace="second-graph")


def test_default_schema_is_adopted_only_by_unconsumed_schema_less_context():
    """Replacement graphs supply behavior without overwriting explicit schemas."""
    default = GraphContext(ContextState)
    fresh = GraphContext()
    fresh._adopt_default_state_schema(default)
    assert fresh._state_schema is ContextState

    explicit = GraphContext(dict)
    explicit._adopt_default_state_schema(default)
    assert explicit._state_schema is dict
