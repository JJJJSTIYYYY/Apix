"""Unit tests for graph construction and transition validation."""

import math

import pytest

from apix.core.event import APIX_HANDLER_REGISTRY
from apix.core.graph import END, START, GraphManager, namespace_set
from apix.core.graph.base import (
    _acquire_namespace,
    _namespace_graphs,
    _release_namespace,
    get_node_name_in_namespace,
)


def source(state):
    return {}


def target(state):
    return {}


def test_add_node_and_add_nodes_are_fluent():
    """Builder registration methods return the same manager instance."""
    manager = GraphManager()

    assert manager.add_node(source) is manager
    assert manager.add_nodes([target]) is manager


@pytest.mark.parametrize(
    ("timeout", "expected"),
    [
        (None, None),
        (0, None),
        (-1, None),
        (1, 1.0),
        (1.5, 1.5),
    ],
)
def test_add_node_stores_normalised_timeout(timeout, expected):
    """Node timeouts are graph-specific and non-positive means unlimited."""
    manager = GraphManager().add_node(source, timeout=timeout)

    assert manager._node_timeouts["source"] == expected


@pytest.mark.parametrize("timeout", [True, "1", object()])
def test_add_node_rejects_non_numeric_timeout_without_registering_node(timeout):
    """Invalid timeout types leave the manager unchanged."""
    manager = GraphManager()

    with pytest.raises(TypeError, match="timeout must be a number or None"):
        manager.add_node(source, timeout=timeout)

    assert manager.has_node("source") is False


@pytest.mark.parametrize("timeout", [math.inf, -math.inf, math.nan])
def test_add_node_rejects_non_finite_timeout_without_registering_node(timeout):
    """NaN and infinity cannot represent executable deadlines."""
    manager = GraphManager()

    with pytest.raises(ValueError, match="timeout must be finite"):
        manager.add_node(source, timeout=timeout)

    assert manager.has_node("source") is False


@pytest.mark.parametrize("reserved_name", [START, END])
def test_reserved_node_names_are_rejected(reserved_name):
    """User nodes cannot replace the predefined START and END nodes."""
    with pytest.raises(ValueError, match="reserved graph node name"):
        GraphManager().add_node(source, reserved_name)


def test_duplicate_node_name_is_rejected():
    """Every user node name must be unique."""
    manager = GraphManager().add_node(source)

    with pytest.raises(ValueError, match="already registered"):
        manager.add_node(target, "source")


@pytest.mark.parametrize(
    ("left", "right", "message"),
    [
        ("missing", END, "has not been added"),
        (START, "missing", "has not been added"),
        (END, START, "cannot have an outgoing transition"),
    ],
)
def test_edge_endpoints_must_exist_and_end_cannot_be_a_source(left, right, message):
    """Edges validate both endpoints and the terminal END constraint."""
    with pytest.raises(ValueError, match=message):
        GraphManager().add_edge(left, right)


def test_only_one_manager_transition_is_allowed_per_source():
    """A source cannot have two direct or generated outgoing transitions."""
    manager = GraphManager().add_nodes([source, target]).add_edge(START, "source")

    with pytest.raises(ValueError, match="already has an outgoing transition"):
        manager.add_edge(START, "target")


def test_condition_must_be_callable():
    """Conditional edges reject non-callable predicates."""
    manager = GraphManager().add_nodes([source, target])

    with pytest.raises(TypeError, match="condition.*callable"):
        manager.add_edge("source", "target", condition=True)


def test_generated_condition_name_avoids_user_node_collision():
    """Generated helper nodes receive a suffix when their base name exists."""
    def predicate(state):
        return True

    manager = (
        GraphManager()
        .add_nodes([source, target])
        .add_node(lambda state: {}, "__condition__source__predicate")
    )

    manager.add_edge("source", "target", predicate)

    assert "__condition__source__predicate_2" in manager._nodes


def test_router_requires_at_least_one_target():
    """A router without declared destinations cannot be constructed."""
    manager = GraphManager().add_node(source)

    with pytest.raises(ValueError, match="at least one target"):
        manager.add_router("source", [], lambda state: END)


def test_router_targets_must_exist():
    """Every declared router destination must be a known node or END."""
    manager = GraphManager().add_node(source)

    with pytest.raises(ValueError, match="has not been added"):
        manager.add_router("source", ["missing"], lambda state: "missing")


def test_router_must_be_callable():
    """Router definitions reject non-callable selectors."""
    manager = GraphManager().add_nodes([source, target])

    with pytest.raises(TypeError, match="router.*callable"):
        manager.add_router("source", ["target"], router="target")


def test_compile_requires_start_transition():
    """A compiled graph must have an entry transition from START."""
    with pytest.raises(ValueError, match="outgoing transition from `START`"):
        GraphManager().add_node(source).compile_graph()


def test_compile_forwards_node_timeouts_to_runtime():
    """The compiled graph retains the manager's per-node timeout policy."""
    graph = (
        GraphManager()
        .add_node(source, timeout=2.5)
        .add_edge(START, "source")
        .compile_graph()
    )

    assert graph._node_timeouts == {"source": 2.5}


@pytest.mark.parametrize(
    ("using_namespace", "expected"),
    [(None, ""), ("", ""), ("agent-runtime", "agent-runtime")],
)
def test_compile_forwards_listener_namespace(using_namespace, expected):
    """GraphManager exposes NodeGraph's listener namespace selection."""
    graph = (
        GraphManager()
        .add_node(source)
        .add_edge(START, "source")
        .compile_graph(using_namespace=using_namespace)
    )

    assert graph._listener_namespace == expected
    assert expected in namespace_set
    assert _namespace_graphs[expected] is graph


def test_compile_rejects_occupied_namespace_by_default():
    """An existing compiled graph is retained when replacement is disabled."""
    first_graph = (
        GraphManager()
        .add_node(source)
        .add_edge(START, "source")
        .compile_graph(using_namespace="occupied")
    )

    with pytest.raises(ValueError, match="already in use"):
        (
            GraphManager()
            .add_node(target)
            .add_edge(START, "target")
            .compile_graph(using_namespace="occupied")
        )

    assert first_graph._decomposed is False
    assert _namespace_graphs["occupied"] is first_graph


def test_acquire_namespace_rejects_conflict_before_calling_factory():
    """A rejected acquisition cannot construct or replace another graph."""
    first_graph = (
        GraphManager()
        .add_node(source)
        .add_edge(START, "source")
        .compile_graph(using_namespace="factory-conflict")
    )
    factory_called = False

    def graph_factory():
        nonlocal factory_called
        factory_called = True
        return first_graph

    with pytest.raises(ValueError, match="already in use"):
        _acquire_namespace("factory-conflict", graph_factory)

    assert factory_called is False
    assert _namespace_graphs["factory-conflict"] is first_graph


def test_acquire_namespace_does_not_register_failed_factory():
    """Construction failure leaves an unoccupied namespace unacquired."""
    def graph_factory():
        raise RuntimeError("construction failed")

    with pytest.raises(RuntimeError, match="construction failed"):
        _acquire_namespace("factory-failure", graph_factory)

    assert "factory-failure" not in namespace_set
    assert "factory-failure" not in _namespace_graphs


def test_compile_exist_ok_decomposes_and_replaces_original_graph():
    """Replacement unregisters the old listeners before installing new ones."""
    first_graph = (
        GraphManager()
        .add_node(source, "shared")
        .add_edge(START, "shared")
        .compile_graph(using_namespace="replaceable")
    )
    first_callbacks = {
        APIX_HANDLER_REGISTRY.get_handler(handler_name).callback
        for handler_name in APIX_HANDLER_REGISTRY.get_handlers_chain_for_event(
            get_node_name_in_namespace("shared", "replaceable")
        )
    }

    replacement = (
        GraphManager()
        .add_node(target, "shared")
        .add_edge(START, "shared")
        .compile_graph(
            using_namespace="replaceable",
            exist_ok=True,
        )
    )
    replacement_callbacks = {
        APIX_HANDLER_REGISTRY.get_handler(handler_name).callback
        for handler_name in APIX_HANDLER_REGISTRY.get_handlers_chain_for_event(
            get_node_name_in_namespace("shared", "replaceable")
        )
    }

    assert first_graph._decomposed is True
    assert first_graph._listener_handler_names == []
    assert first_callbacks.isdisjoint(replacement_callbacks)
    assert len(replacement_callbacks) == 1
    assert namespace_set == {"replaceable"}
    assert _namespace_graphs["replaceable"] is replacement

    _release_namespace(first_graph)
    assert namespace_set == {"replaceable"}
    assert _namespace_graphs["replaceable"] is replacement


def test_decompose_releases_namespace_by_contextmanager():
    graph = (
        GraphManager()
        .add_node(source)
        .add_edge(START, "source")
        .compile_graph(using_namespace="reusable")
    )

    assert "reusable" in namespace_set
    assert "reusable" in _namespace_graphs

    with graph:
        pass

    assert "reusable" not in namespace_set
    assert "reusable" not in _namespace_graphs
    assert True == graph._decomposed


def test_decompose_releases_namespace_for_later_compile():
    """Direct decomposition keeps GraphManager's global index synchronized."""
    first_graph = (
        GraphManager()
        .add_node(source)
        .add_edge(START, "source")
        .compile_graph(using_namespace="reusable")
    )

    assert "reusable" in namespace_set
    assert "reusable" in _namespace_graphs

    first_graph.decompose()

    assert "reusable" not in namespace_set
    assert "reusable" not in _namespace_graphs

    replacement = (
        GraphManager()
        .add_node(target)
        .add_edge(START, "target")
        .compile_graph(using_namespace="reusable")
    )
    assert _namespace_graphs["reusable"] is replacement


def test_none_and_empty_string_share_global_namespace():
    """Both global namespace spellings participate in one uniqueness check."""
    (
        GraphManager()
        .add_node(source)
        .add_edge(START, "source")
        .compile_graph(using_namespace=None)
    )

    with pytest.raises(ValueError, match="<global>"):
        (
            GraphManager()
            .add_node(target)
            .add_edge(START, "target")
            .compile_graph(using_namespace="")
        )
