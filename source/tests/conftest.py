"""Shared pytest isolation for process-global runtime registries."""

import pytest

from apix.core.event import apix_handler_registry
from apix.core.graph.base import _namespace_graphs, namespace_set


def _clear_node_graph_listeners() -> None:
    """Remove listeners registered by NodeGraph instances from prior tests."""
    for graph in tuple(_namespace_graphs.values()):
        graph.decompose()
    _namespace_graphs.clear()
    namespace_set.clear()

    handler_names = {
        name
        for name in apix_handler_registry.registry
        if name.startswith("graph_listener_")
    }
    for handler_name in handler_names:
        apix_handler_registry.delete_handler_from_registry(handler_name)


@pytest.fixture(autouse=True)
def isolate_node_graph_listeners():
    """Give every test a clean global NodeGraph listener namespace."""
    _clear_node_graph_listeners()
    yield
    _clear_node_graph_listeners()
