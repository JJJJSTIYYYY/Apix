"""Executable example of extending NodeGraph through event subscriptions."""

import pytest
import pytest_asyncio

from apix.core.event import (
    ApixEvent,
    apix_handler_registry,
    delete_handler_from_registry,
    subscribe,
)
from apix.core.event.event_loop import apix_event_loop
from apix.core.event import EVENT_PIPE
from apix.core.graph import START, GraphManager


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(
    autouse=True,
    scope="module",
    loop_scope="session",
)
async def stop_event_loop_after_module():
    """Stop and clear the shared event runtime after this module."""
    yield
    await apix_event_loop.stop()
    await EVENT_PIPE.clear()


async def test_subscribe_inserts_plugin_before_node_graph_listener():
    """Use between_handlers to place a plugin in a node's event pipeline."""
    node_name = "plugin_demo_business_node"

    def business_node(state: dict) -> dict:
        """Represent the application node that receives plugin-enriched state."""
        return {
            "pipeline": [*state["pipeline"], "business-node"],
            "plugin_value_seen": state["plugin_value"],
        }

    graph = (
        GraphManager()
        .add_node(business_node, node_name)
        .add_edge(START, node_name)
        .compile_graph()
    )

    # Compiling NodeGraph registers one event handler for the business node.
    [node_graph_handler_name] = (
        apix_handler_registry.get_handlers_chain_for_event(node_name)
    )
    node_graph_handler = apix_handler_registry.get_handler(
        node_graph_handler_name
    )

    # A higher priority makes this handler the left boundary of the plugin
    # insertion range; NodeGraph listeners use the default priority of 1.
    @subscribe(node_name, priority=10)
    async def plugin_demo_authentication(event: ApixEvent) -> None:
        event.context.state["pipeline"].append("authentication-plugin")

    # A plugin is just another event subscriber. Function names identify the
    # two existing handlers between which it should be inserted.
    @subscribe(
        node_name,
        between_handlers=(
            plugin_demo_authentication.__name__,
            node_graph_handler.name,
        ),
    )
    async def plugin_demo_enrichment(event: ApixEvent) -> None:
        state = event.context.state
        state["pipeline"].append("enrichment-plugin")
        state["plugin_value"] = "injected through event plugin"

    handler_names = apix_handler_registry.get_handlers_chain_for_event(
        node_name
    )
    assert handler_names == [
        plugin_demo_authentication.__name__,
        plugin_demo_enrichment.__name__,
        node_graph_handler.name,
    ]

    plugin_meta = apix_handler_registry.get_handler(
        plugin_demo_enrichment.__name__
    )
    assert plugin_meta.between_handlers == (
        plugin_demo_authentication.__name__,
        node_graph_handler.name,
    )
    assert plugin_meta.priority is None

    assert await graph.invoke({"pipeline": []}) == {
        "pipeline": [
            "authentication-plugin",
            "enrichment-plugin",
            "business-node",
        ],
        "plugin_value": "injected through event plugin",
        "plugin_value_seen": "injected through event plugin",
    }
    graph.decompose()
    delete_handler_from_registry(plugin_demo_authentication.__name__)
    delete_handler_from_registry(plugin_demo_enrichment.__name__)
