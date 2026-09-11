"""Executable example of extending NodeGraph through event subscriptions."""

import pytest
import pytest_asyncio

from apix.core.event import (
    ApixEvent,
    APIX_HANDLER_REGISTRY,
    unsubscribe,
    subscribe,
)
from apix.core.event.event_loop import APIX_EVENT_LOOP
from apix.core.event import EVENT_PIPE
from apix.core.graph import GRAPH_DISPATCH, START, GraphManager


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(
    autouse=True,
    scope="module",
    loop_scope="session",
)
async def stop_event_loop_after_module():
    """Stop and clear the shared event runtime after this module."""
    yield
    await APIX_EVENT_LOOP.stop()
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

    # Compiling NodeGraph registers one shared dispatch handler. Plugins
    # observe the dispatch event and inspect target_node_name to decide
    # whether they should act on a specific graph node.
    [node_graph_handler_name] = (
        APIX_HANDLER_REGISTRY.get_handlers_chain_for_event(GRAPH_DISPATCH)
    )
    node_graph_handler = APIX_HANDLER_REGISTRY.get_handler(
        node_graph_handler_name
    )

    # A higher priority makes this handler the left boundary of the plugin
    # insertion range; NodeGraph listeners use the default priority of 1.
    @subscribe(GRAPH_DISPATCH, priority=10)
    async def plugin_demo_authentication(event: ApixEvent) -> None:
        if event.context.target_node_name != node_name:
            return
        event.context.state["pipeline"].append("authentication-plugin")

    # A plugin is just another event subscriber. Function names identify the
    # two existing handlers between which it should be inserted.
    @subscribe(
        GRAPH_DISPATCH,
        between_handlers=(
            plugin_demo_authentication.__name__,
            node_graph_handler.name,
        ),
    )
    async def plugin_demo_enrichment(event: ApixEvent) -> None:
        if event.context.target_node_name != node_name:
            return
        state = event.context.state
        state["pipeline"].append("enrichment-plugin")
        state["plugin_value"] = "injected through event plugin"

    handler_names = APIX_HANDLER_REGISTRY.get_handlers_chain_for_event(
        GRAPH_DISPATCH
    )
    assert handler_names == [
        plugin_demo_authentication.__name__,
        plugin_demo_enrichment.__name__,
        node_graph_handler.name,
    ]

    plugin_meta = APIX_HANDLER_REGISTRY.get_handler(
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
    unsubscribe(plugin_demo_authentication.__name__)
    unsubscribe(plugin_demo_enrichment.__name__)


@pytest.mark.parametrize("mode", ["invoke", "stream"])
@pytest.mark.parametrize("action", ["error", "timeout", "accept", "accept_and_error"])
@pytest.mark.parametrize("target", [START, "business", "END"])
async def test_upstream_plugin_termination_completes_graph(mode, action, target):
    """Public subscriptions must not leave invoke or stream waiting forever."""
    import asyncio

    from apix.core.graph import END
    from apix.core.graph.context import GraphContext, get_stream_writer
    from apix.core.utils.exception import GraphNodeError

    called = []

    def business(state):
        called.append("business")
        get_stream_writer()("business chunk")
        return {"value": "updated"}

    graph = (
        GraphManager().add_node(business).add_edge(START, "business")
        .add_edge("business", END).compile_graph()
    )
    target_name = END if target == "END" else target
    captured_events = []

    @subscribe(GRAPH_DISPATCH, priority=10, time_out=0.01)
    async def termination_plugin(event):
        if event.context.target_node_name != target_name:
            return
        captured_events.append(event)
        if action in ("accept", "accept_and_error"):
            event.accept()
        if action in ("error", "accept_and_error"):
            raise ValueError("plugin rejected dispatch")
        if action == "timeout":
            await asyncio.Future()

    context = GraphContext()
    chunks = []

    async def run():
        if mode == "invoke":
            return await graph.invoke({"value": "initial"}, context)
        async for chunk in graph.stream({"value": "initial"}, context):
            chunks.append(chunk)

    try:
        async with asyncio.timeout(1):
            if action == "accept":
                result = await run()
                assert context.status == "aborted"
                if mode == "invoke":
                    assert result == {"value": "initial"}
            else:
                with pytest.raises(GraphNodeError) as raised:
                    await run()
                assert context.status == "failed"
                [error] = raised.value.errors
                assert error.handler_name == "termination_plugin"
                assert error.exception_type == ("TimeoutError" if action == "timeout" else "ValueError")
        assert len(captured_events) == 1
        assert context.completion.done()
        assert not context.is_active
        assert graph._invocation_count == 0
        assert called == (["business"] if target == "END" else [])
        if mode == "stream":
            assert chunks == (["business chunk"] if target == "END" else [])
    finally:
        unsubscribe(termination_plugin.__name__)
        graph.decompose()


@pytest.mark.parametrize("mode", ["invoke", "stream"])
async def test_graph_dispatch_handles_its_own_snapshot_failure(mode):
    """A failure before node execution completes through on_error."""
    import asyncio
    from unittest.mock import patch

    from apix.core.graph.context import GraphContext

    called = []

    def business(state):
        called.append("business")
        return state

    graph = GraphManager().add_node(business).add_edge(START, "business").compile_graph()
    context = GraphContext()

    async def run():
        if mode == "invoke":
            return await graph.invoke({}, context)
        return [chunk async for chunk in graph.stream({}, context)]

    try:
        with patch.object(GraphContext, "take_a_snapshot", side_effect=ValueError("snapshot failed")):
            async with asyncio.timeout(1):
                with pytest.raises(ValueError, match="snapshot failed"):
                    await run()
        assert context.status == "failed"
        assert context.completion.done()
        assert called == []
        assert graph._invocation_count == 0
    finally:
        graph.decompose()


async def test_background_plugin_failure_does_not_fail_graph():
    """A failed background plugin cannot suppress the graph dispatch core."""
    import asyncio

    from apix.core.graph.context import GraphContext

    failed = asyncio.Event()

    def business(state):
        return {"completed": True}

    graph = GraphManager().add_node(business).add_edge(START, "business").compile_graph()

    @subscribe(GRAPH_DISPATCH, priority=20, background=True)
    async def background_plugin(event):
        if event.context.target_node_name == START:
            failed.set()
            raise ValueError("optional background work failed")

    @subscribe(GRAPH_DISPATCH, priority=10)
    async def wait_for_background_plugin(event):
        await failed.wait()

    context = GraphContext()
    try:
        async with asyncio.timeout(1):
            assert await graph.invoke({}, context) == {"completed": True}
        assert context.status == "finished"
    finally:
        unsubscribe(background_plugin.__name__)
        unsubscribe(wait_for_background_plugin.__name__)
        graph.decompose()


@pytest.mark.parametrize("action", ["error", "accept", "accept_and_error", "hook_error", "hook_timeout"])
@pytest.mark.parametrize("timeout", [None, 10])
async def test_interruption_hook_termination_unblocks_node(action, timeout):
    """Interruption notifications release the Block as well as the invocation."""
    import asyncio

    from apix.core.graph.context import GraphContext
    from apix.core.graph.interrupter.graph_interrupter import interrupt
    from apix.core.utils.exception import GraphNodeError

    resumed = []
    blocks = []
    hook_called = []

    async def business(state):
        await interrupt(timeout=timeout)
        resumed.append(True)
        return state

    graph = GraphManager().add_node(business).add_edge(START, "business").compile_graph()

    @subscribe("graph__interrupted", priority=10)
    async def interruption_plugin(event):
        blocks.append(event.context)
        if action in ("accept", "accept_and_error"):
            event.accept()
        if action in ("error", "accept_and_error"):
            raise ValueError("upstream interruption failed")

    async def on_interrupted(block):
        hook_called.append(True)
        if action == "hook_timeout":
            raise TimeoutError("hook timeout")
        raise ValueError("hook failed locally")

    graph.add_interrupted_hook(on_interrupted)
    context = GraphContext()
    try:
        async with asyncio.timeout(1):
            if action == "accept":
                assert await graph.invoke({"value": "initial"}, context) == {"value": "initial"}
                assert context.status == "aborted"
            else:
                error_type = {
                    "hook_error": ValueError,
                    "hook_timeout": TimeoutError,
                }.get(action, GraphNodeError)
                with pytest.raises(error_type):
                    await graph.invoke({}, context)
                assert context.status == "failed"
        assert resumed == []
        assert hook_called == ([True] if action in ("hook_error", "hook_timeout") else [])
        assert len(blocks) == 1 and blocks[0].done
        assert blocks[0].cancelled is (action == "accept")
    finally:
        unsubscribe(interruption_plugin.__name__)
        graph.decompose()
