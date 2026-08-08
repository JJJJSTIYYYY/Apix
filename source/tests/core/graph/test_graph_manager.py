"""Unit tests for graph construction and transition validation."""

import math

import pytest

from apix.core.graph import END, START, GraphManager


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
