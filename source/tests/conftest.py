"""Shared pytest isolation for process-global runtime registries."""

import asyncio

import pytest
import pytest_asyncio

from apix.core.event import APIX_HANDLER_REGISTRY, APIX_EVENT_LOOP, EVENT_PIPE
from apix.core.graph.base import _namespace_graphs, namespace_set


def _clear_node_graph_listeners() -> None:
    """Remove listeners registered by NodeGraph instances from prior tests."""
    for graph in tuple(_namespace_graphs.values()):
        graph.decompose()
    _namespace_graphs.clear()
    namespace_set.clear()

    handler_names = {
        name
        for name in APIX_HANDLER_REGISTRY.registry
        if name.startswith("graph_listener_")
    }
    for handler_name in handler_names:
        APIX_HANDLER_REGISTRY.unregister_handler(handler_name)


@pytest.fixture(autouse=True)
def isolate_node_graph_listeners():
    """Give every test a clean global NodeGraph listener namespace."""
    _clear_node_graph_listeners()
    yield
    _clear_node_graph_listeners()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def cleanup_event_runtime(isolate_node_graph_listeners):
    """Release test-owned tasks explicitly now that stop only halts consumption."""
    yield
    await APIX_EVENT_LOOP.stop()
    tasks = list(APIX_EVENT_LOOP._dispatch_tasks | APIX_EVENT_LOOP._background_handler_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await EVENT_PIPE.clear()
