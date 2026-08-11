"""Shared pytest isolation for process-global runtime registries."""

import pytest

from apix.core.event import apix_event_registry
from apix.core.graph.base import _namespace_graphs, namespace_set


def _clear_node_graph_listeners() -> None:
    """Remove listeners registered by NodeGraph instances from prior tests."""
    for graph in tuple(_namespace_graphs.values()):
        graph.decompose()
    _namespace_graphs.clear()
    namespace_set.clear()

    handler_names = {
        name
        for name in apix_event_registry._handlers_meta
        if name.startswith("graph_listener_")
    }
    if not handler_names:
        return

    for event_name, handlers in list(apix_event_registry._handlers.items()):
        retained_handlers = [
            handler
            for handler in handlers
            if handler.name not in handler_names
        ]
        if retained_handlers:
            apix_event_registry._handlers[event_name] = retained_handlers
        else:
            apix_event_registry._handlers.pop(event_name)

    for handler_name in handler_names:
        apix_event_registry._handlers_meta.pop(handler_name, None)


@pytest.fixture(autouse=True)
def isolate_node_graph_listeners():
    """Give every test a clean global NodeGraph listener namespace."""
    _clear_node_graph_listeners()
    yield
    _clear_node_graph_listeners()
