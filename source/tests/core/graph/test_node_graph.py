"""Focused unit tests for NodeGraph defensive runtime behaviour."""

import asyncio
from typing import Annotated, TypedDict

import pytest

from apix.core.event import (
    apix_event_loop,
    apix_event_registry,
    event_pipe_writer,
)
from apix.core.utils.exception import EventHandlerAlreadyRegisteredError
from apix.core.graph import (
    AutoMerge,
    Command,
    END,
    START,
    Node,
    NodeGraph,
    Reset,
)
from apix.core.graph.context import GraphContext
from apix.core.graph.context import noop_stream_writer


def _graph_context(
    state=None,
    state_schema: type | None = None,
) -> GraphContext:
    """Build the minimal context required by apply_command."""
    context = GraphContext(state_schema)
    context.state = state if state is not None else {}
    return context


def _bound_context(
    graph: NodeGraph,
    run_id: str,
    state: dict,
    *,
    steps: int = 0,
) -> GraphContext:
    """Build a fully bound context for lifecycle unit tests."""
    context = GraphContext()
    context._bind(
        context_namespace=graph._listener_namespace,
        run_id=run_id,
        state=state,
        completion=asyncio.get_running_loop().create_future(),
        stream_writer=noop_stream_writer(),
    )
    context.steps = steps
    return context


def test_apply_command_rejects_non_dict_update():
    """NodeGraph defensively validates commands from external callers."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="Command.update must be a dict"):
        graph.apply_command(Command(update=[]), START, _graph_context())


@pytest.mark.parametrize("using_namespace", [None, ""])
def test_empty_listener_namespace_uses_global_namespace(using_namespace):
    """None and an empty string both select the global listener namespace."""
    graph = NodeGraph(
        {},
        {START: END},
        using_namespace=using_namespace,
    )

    assert graph._listener_namespace == ""


def test_listener_namespace_uses_supplied_value():
    """A non-empty listener namespace is retained without random suffixes."""
    graph = NodeGraph(
        {},
        {START: END},
        using_namespace="agent-runtime",
    )

    assert graph._listener_namespace == "agent-runtime"


def test_reserved_global_namespace_token_is_rejected():
    """The display-only global namespace label cannot become a real name."""
    with pytest.raises(ValueError, match="preserved namespace"):
        NodeGraph({}, {START: END}, using_namespace="<global>")


def test_set_max_steps_is_fluent_and_updates_runtime_limit():
    """The compatibility setter returns the graph and changes its limit."""
    graph = NodeGraph({}, {START: END})

    assert graph.set_max_steps(7) is graph
    assert graph._max_steps == 7


def test_apply_command_rejects_non_string_goto():
    """A direct apply_command call cannot route to a non-string target."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="Command.goto must be a string or None"):
        graph.apply_command(Command(goto=1), START, _graph_context())


def test_apply_command_rejects_plain_dict():
    """Only Command instances satisfy the direct runtime contract."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="must return a Command"):
        graph.apply_command({}, START, _graph_context())


class AutoMergeState(TypedDict):
    """State schema used to exercise annotated update behaviour."""

    values: Annotated[list[int], AutoMerge()]
    total: Annotated[int, AutoMerge]
    replaced: list[int]


class MissingAdd:
    """AutoMerge value whose addition protocol is deliberately unavailable."""

    __add__ = None


class UnsupportedAdd:
    """AutoMerge value that rejects the supplied update type."""

    def __add__(self, value):
        return NotImplemented


def test_apply_command_auto_increases_annotated_fields():
    """Marked existing fields call __add__; unmarked fields are replaced."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )
    context = _graph_context(
        {
            "values": [1],
            "total": 2,
            "replaced": [1],
        },
        AutoMergeState,
    )

    state, next_node = graph.apply_command(
        Command(
            update={
                "values": [2, 3],
                "total": 4,
                "replaced": [2],
            }
        ),
        START,
        context,
    )

    assert state == {
        "values": [1, 2, 3],
        "total": 6,
        "replaced": [2],
    }
    assert next_node == END
    assert context.state == {
        "values": [1],
        "total": 2,
        "replaced": [1],
    }


def test_apply_command_initializes_missing_auto_increase_field():
    """A marked field without a current value is assigned directly."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )

    state, _ = graph.apply_command(
        Command(update={"values": [1]}),
        START,
        _graph_context(state_schema=AutoMergeState),
    )

    assert state == {"values": [1]}


def test_auto_merge_requires_callable_add_method():
    """A marked current value must expose a callable addition protocol."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )

    with pytest.raises(TypeError, match="does not provide a callable __add__"):
        graph.apply_command(
            Command(update={"values": [1]}),
            START,
            _graph_context(
                {"values": MissingAdd()},
                AutoMergeState,
            ),
        )


def test_auto_merge_rejects_not_implemented_addition():
    """NotImplemented becomes a useful state merge error."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )

    with pytest.raises(TypeError, match="could not add an update"):
        graph.apply_command(
            Command(update={"values": [1]}),
            START,
            _graph_context(
                {"values": UnsupportedAdd()},
                AutoMergeState,
            ),
        )


def test_replace_bypasses_auto_increase_and_is_unwrapped():
    """Reset forces assignment for both marked and ordinary fields."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )
    context = _graph_context(
        {
            "values": [1, 2],
            "replaced": [1, 2],
        },
        AutoMergeState,
    )

    state, _ = graph.apply_command(
        Command(
            update={
                "values": Reset([3]),
                "replaced": Reset([4]),
            }
        ),
        START,
        context,
    )

    assert state == {
        "values": [3],
        "replaced": [4],
    }
    assert context.state == {
        "values": [1, 2],
        "replaced": [1, 2],
    }


def test_replace_initializes_missing_auto_increase_field():
    """Reset is also unwrapped when the marked field has no old value."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )

    state, _ = graph.apply_command(
        Command(update={"values": Reset([1])}),
        START,
        _graph_context(state_schema=AutoMergeState),
    )

    assert state == {"values": [1]}


def test_node_graph_rejects_non_class_state_schema():
    """Annotated metadata must come from a schema class."""
    with pytest.raises(
        TypeError,
        match="state_schema.*class or None",
    ):
        NodeGraph(
            {},
            {START: END},
            state_schema={},
        )


def test_state_schema_metadata_lives_on_graph_context():
    """NodeGraph retains only a factory for invocation-local state behavior."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )
    context = graph._context_factory()

    assert not hasattr(graph, "_state_schema")
    assert not hasattr(graph, "_auto_increase_keys")
    assert not hasattr(graph, "_keep_ref_keys")
    assert context._state_schema is AutoMergeState
    assert context._auto_increase_keys == frozenset({"values", "total"})
    assert context._keep_ref_keys == frozenset()


def test_node_graph_rejects_timeout_for_unknown_node():
    """Direct construction validates every timeout target."""
    with pytest.raises(ValueError, match="unknown nodes: missing"):
        NodeGraph(
            {},
            {START: END},
            node_timeouts={"missing": 1},
        )


@pytest.mark.asyncio
async def test_finish_and_fail_do_not_replace_completed_future():
    """Late END or failure events cannot overwrite an invocation result."""
    graph = NodeGraph({}, {START: END})
    context = _bound_context(
        graph,
        "test-run",
        {"replacement": True},
    )
    completion = context.completion
    assert completion is not None
    completion.set_result({"original": True})

    graph._finish(context)
    graph._fail(context, RuntimeError("late failure"))

    assert await completion == {"original": True}


@pytest.mark.parametrize(
    "context",
    [
        None,
        {},
        GraphContext(),
        {"run_id": 1, "state": {}, "completion": None},
        {"run_id": "run", "state": [], "completion": None},
        {"run_id": "run", "state": {}, "completion": None},
    ],
)
def test_is_active_context_rejects_malformed_event_context(context):
    """Graph listeners ignore events that do not carry a valid run context."""
    graph = NodeGraph({}, {START: END})

    assert graph._is_active_context(context) is False


def test_is_active_context_rejects_owned_but_unbound_context():
    """Ownership alone is insufficient without invocation runtime fields."""
    graph = NodeGraph({}, {START: END})
    context = GraphContext()
    context._context_namespace = graph._listener_namespace

    assert graph._is_active_context(context) is False


@pytest.mark.asyncio
async def test_is_active_context_uses_context_lifecycle_as_source_of_truth():
    """Completed contexts need no duplicate graph-owned run registry."""
    graph = NodeGraph({}, {START: END})
    context = _bound_context(graph, "completed-run", {"value": 1})
    assert graph._is_active_context(context) is True

    context.abort()

    assert graph._is_active_context(context) is False
    assert not hasattr(graph, "_active_runs")
    assert not hasattr(graph, "_active_runs_lock")


@pytest.mark.asyncio
async def test_abort_rejects_non_context():
    """Abort accepts a GraphContext rather than an identifier."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="requires a GraphContext"):
        await graph.abort("missing")


@pytest.mark.asyncio
async def test_abort_rejects_unbound_context():
    """An unbound context cannot identify a graph invocation."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(ValueError, match="not active in this graph"):
        await graph.abort(GraphContext())


@pytest.mark.asyncio
async def test_abort_rejects_context_for_inactive_run():
    """A retained or foreign context cannot abort an inactive graph run."""
    graph = NodeGraph({}, {START: END})
    context = _bound_context(graph, "inactive-run", {"checkpoint": 1})
    context.abort()

    with pytest.raises(ValueError, match="not active in this graph"):
        await graph.abort(context)

    completion = context.completion
    assert completion is not None
    assert completion.done()


@pytest.mark.asyncio
async def test_abort_finishes_active_run_with_saved_snapshot():
    """Abort resolves completion and lifecycle immediately becomes inactive."""
    graph = NodeGraph({}, {START: END})
    context = _bound_context(
        graph,
        "active-run",
        {"history": ["saved"]},
        steps=2,
    )
    completion = context.completion
    assert completion is not None
    context.node_name = "retry"
    context.take_a_snapshot()

    await graph.abort(context)

    result = await completion
    assert result == {"history": ["saved"]}
    assert result is not context.state
    assert graph._is_active_context(context) is False


@pytest.mark.asyncio
async def test_abort_cannot_finish_same_run_twice():
    """A completed context cannot be aborted through the graph twice."""
    graph = NodeGraph({}, {START: END})
    context = _bound_context(graph, "active-run", {})
    context.node_name = "retry"
    context.take_a_snapshot()

    await graph.abort(context)

    with pytest.raises(ValueError, match="not active in this graph"):
        await graph.abort(context)


@pytest.mark.asyncio
async def test_invoke_rejects_non_context_argument():
    """The optional invocation context has an explicit runtime type contract."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="GraphContext or None"):
        await graph.invoke({}, {})


@pytest.mark.asyncio
async def test_cancel_before_bind_does_not_abort_pending_context(monkeypatch):
    """Cancellation during event-loop startup leaves an unbound context pending."""
    graph = NodeGraph({}, {START: END})
    context = GraphContext()

    async def cancel_start():
        raise asyncio.CancelledError

    monkeypatch.setattr(apix_event_loop, "start", cancel_start)

    with pytest.raises(asyncio.CancelledError):
        await graph.invoke({}, context)

    assert context.status == "pending"
    assert context.is_bound is False


@pytest.mark.asyncio
async def test_post_failure_marks_running_context_failed(monkeypatch):
    """A setup failure after binding resolves the context as failed."""
    graph = NodeGraph({}, {START: END})
    context = GraphContext()
    error = RuntimeError("post failed")

    async def fail_post(node_name, bound_context):
        raise error

    monkeypatch.setattr(graph, "_post_next", fail_post)

    with pytest.raises(RuntimeError, match="post failed"):
        await graph.invoke({}, context)

    assert context.status == "failed"
    assert context.completion is not None
    with pytest.raises(RuntimeError, match="post failed"):
        await context.completion
    await apix_event_loop.stop()


@pytest.mark.asyncio
async def test_execute_start_ignores_error_after_attempt_becomes_stale(monkeypatch):
    """A stale START failure cannot overwrite an aborted result."""
    graph = NodeGraph({}, {START: END})
    context = _bound_context(graph, "stale-start", {"saved": True})
    completion = context.completion
    assert completion is not None

    async def abort_then_fail(node_name, bound_context):
        bound_context.abort()
        raise RuntimeError("late start failure")

    monkeypatch.setattr(graph, "_post_next", abort_then_fail)

    await graph._execute_start(context)

    assert await completion == {"saved": True}
    assert context.status == "aborted"


@pytest.mark.asyncio
async def test_execute_node_ignores_error_after_attempt_becomes_stale():
    """A late node error cannot fail an already aborted attempt."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def fail_late(state):
        started.set()
        await release.wait()
        raise RuntimeError("late node failure")

    graph = NodeGraph(
        {"node": Node(fail_late)},
        {START: "node", "node": END},
    )
    context = _bound_context(graph, "stale-node", {"saved": True})
    completion = context.completion
    assert completion is not None

    execution = asyncio.create_task(graph._execute_node("node", context))
    await started.wait()
    context.abort()
    release.set()
    await execution

    assert await completion == {"saved": True}
    assert context.status == "aborted"
    assert context.context_snapshot is not None
    assert context.context_snapshot["node_name"] == START


@pytest.mark.asyncio
async def test_post_next_failure_needs_no_quiescence_rollback(monkeypatch):
    """Posting failures no longer interact with deleted recovery counters."""
    graph = NodeGraph({}, {START: END})
    context = GraphContext()

    async def fail_post_event(**kwargs):
        raise RuntimeError("event pipe unavailable")

    monkeypatch.setattr(event_pipe_writer, "post_event", fail_post_event)

    with pytest.raises(RuntimeError, match="event pipe unavailable"):
        await graph._post_next(END, context)

    assert context.node_name == END
    assert not hasattr(context, "_pending_events")
    assert not hasattr(context, "_quiescent")


def test_decompose_unregisters_only_graph_handlers_and_is_idempotent():
    """Decomposition removes owned listeners while retaining graph plugins."""
    async def retained_plugin(event):
        pass

    apix_event_registry.subscribe("node")(retained_plugin)
    graph = NodeGraph(
        {"node": Node(lambda state: {})},
        {START: "node", "node": END},
        using_namespace="decompose",
    )
    graph_handler_names = set(graph._listener_handler_names)

    graph.decompose()
    graph.decompose()

    assert graph._decomposed is True
    assert graph._listener_handler_names == []
    assert graph_handler_names.isdisjoint(
        apix_event_registry.get_all_handlers_meta()
    )
    assert [
        handler.name
        for handler in apix_event_registry.get_handlers("node")
    ] == [retained_plugin.__name__]

    apix_event_registry.unsubscribe(retained_plugin.__name__)


def test_listener_registration_failure_rolls_back_partial_handlers():
    """A constructor collision cannot leak listeners registered before it."""
    async def conflicting_handler(event):
        pass

    conflicting_handler.__name__ = "graph_listener_rollback_node"
    apix_event_registry.subscribe("foreign")(conflicting_handler)

    with pytest.raises(EventHandlerAlreadyRegisteredError):
        NodeGraph(
            {"node": Node(lambda state: {})},
            {START: "node", "node": END},
            using_namespace="rollback",
        )

    assert "graph_listener_rollback_START" not in (
        apix_event_registry.get_all_handlers_meta()
    )
    assert apix_event_registry.get_handler_meta(
        conflicting_handler.__name__
    )["subscribe"] == ["foreign"]

    apix_event_registry.unsubscribe(conflicting_handler.__name__)


@pytest.mark.asyncio
async def test_decomposed_graph_rejects_new_invocation():
    """Every public business interface rejects an invalidated graph."""
    graph = NodeGraph({}, {START: END})
    graph.decompose()

    with pytest.raises(RuntimeError, match="has been decomposed"):
        await graph.invoke({})
    with pytest.raises(RuntimeError, match="has been decomposed"):
        await anext(graph.stream({}))
    with pytest.raises(RuntimeError, match="has been decomposed"):
        await graph.abort(GraphContext())
    with pytest.raises(RuntimeError, match="has been decomposed"):
        graph.set_max_steps(1)


@pytest.mark.asyncio(loop_scope="session")
async def test_decompose_rejects_active_invocation():
    """Listeners remain installed until an active invocation completes."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_node(state):
        started.set()
        await release.wait()
        return {"finished": True}

    graph = NodeGraph(
        {"node": Node(blocking_node)},
        {START: "node", "node": END},
        using_namespace="active-decompose",
    )
    invocation = asyncio.create_task(graph.invoke({}))
    await started.wait()

    with pytest.raises(RuntimeError, match="invocations are active"):
        graph.decompose()

    assert graph._decomposed is False
    assert graph._listener_handler_names

    release.set()
    assert await invocation == {"finished": True}
    graph.decompose()
    await apix_event_loop.stop()
