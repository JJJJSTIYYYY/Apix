"""Application contracts at the Apixis runtime boundary."""

import asyncio
from contextlib import aclosing
from typing import Annotated, TypedDict
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from apix.agent.core.graph import AgentGraph, AgentGraphCreator
from apix.agent.core.tool.mcp import mcp_mgr
from apix.agent.core.utils.message import ApixAiMessage, ApixToolMessage
from apixis.core.graph import (
    AutoMerge,
    Command,
    get_current_run_id,
    get_stream_writer,
)
from apixis.core.utils.exception import InvalidContextError


class State(TypedDict, total=False):
    messages: Annotated[list, AutoMerge()]
    value: int


@pytest.fixture
def closed_scopes(monkeypatch):
    close = AsyncMock()
    monkeypatch.setattr(mcp_mgr, "close_agent_scope", close)
    return close


async def test_prepared_and_restored_contexts_close_their_own_scope(closed_scopes):
    runs = []

    def first(state):
        runs.append(get_current_run_id())
        return Command(update={"value": 1}, goto="second")

    def second(state):
        return {"value": state["value"] + 1}

    graph = AgentGraphCreator(State).add_nodes([first, second]).compile_agent("first")
    assert isinstance(graph, AgentGraph)
    context = graph.create_context({"messages": []})
    assert await graph.invoke(graph_context=context) == {"messages": [], "value": 2}
    closed_scopes.assert_awaited_once_with(context.run_id)
    restored = graph.restore_context(context.get_snapshot(0))
    assert await graph.invoke(graph_context=restored) == {"messages": [], "value": 2}
    assert restored.run_id != context.run_id
    assert closed_scopes.await_count == 2


@pytest.mark.parametrize(
    "error", [RuntimeError("node failed"), asyncio.CancelledError()]
)
async def test_failure_and_node_cancellation_close_scope(closed_scopes, error):
    async def fail(state):
        raise error

    graph = AgentGraphCreator(State).add_node(fail).compile_agent("fail")
    context = graph.create_context({"messages": []})
    with pytest.raises(type(error)):
        await graph.invoke(graph_context=context)
    closed_scopes.assert_awaited_once_with(context.run_id)


async def test_rejected_context_reuse_does_not_close_active_scope(closed_scopes):
    started, release = asyncio.Event(), asyncio.Event()

    async def wait(state):
        started.set()
        await release.wait()
        return {}

    graph = AgentGraphCreator(State).add_node(wait).compile_agent("wait")
    context = graph.create_context({"messages": []})
    task = asyncio.create_task(graph.invoke(graph_context=context))
    await asyncio.wait_for(started.wait(), 1)
    try:
        with pytest.raises(InvalidContextError):
            await graph.invoke(graph_context=context)
        with pytest.raises(TypeError):
            await graph.invoke({}, graph_context=context)
        closed_scopes.assert_not_awaited()
    finally:
        release.set()
        await asyncio.wait_for(task, 1)
    closed_scopes.assert_awaited_once_with(context.run_id)


async def test_foreign_context_is_rejected_without_closing_its_scope(closed_scopes):
    first = AgentGraphCreator(State).compile_agent(None)
    second = AgentGraphCreator(State).compile_agent(None)
    assert first.namespace != second.namespace
    context = first.create_context({"messages": []})
    with pytest.raises(InvalidContextError):
        await second.invoke(graph_context=context)
    assert context.status == "pending"
    closed_scopes.assert_not_awaited()


async def test_closing_stream_aborts_context_before_releasing_scope(closed_scopes):
    release = asyncio.Event()

    async def emit(state):
        get_stream_writer()("chunk")
        await release.wait()
        return {}

    graph = AgentGraphCreator(State).add_node(emit).compile_agent("emit")
    context = graph.create_context({"messages": []})
    async with aclosing(graph.stream(graph_context=context)) as stream:
        assert await asyncio.wait_for(anext(stream), 1) == "chunk"
    assert context.status == "aborted"
    closed_scopes.assert_awaited_once_with(context.run_id)
    release.set()


async def test_custom_messages_key_reaches_tool_node(closed_scopes):
    class CustomState(TypedDict):
        conversation: Annotated[list, AutoMerge()]

    def hello():
        return "hello"

    graph = (
        AgentGraphCreator(CustomState, messages_key="conversation")
        .add_tools([hello])
        .compile_agent("tools")
    )
    result = await graph.invoke(
        {
            "conversation": [
                ApixAiMessage(
                    tool_calls=[
                        {"call_id": "hello-1", "tool_name": "hello", "args": {}}
                    ]
                )
            ]
        }
    )
    assert isinstance(result["conversation"][-1], ApixToolMessage)
    assert result["conversation"][-1].content == "hello"


async def test_server_lifespan_can_restart_and_reports_transport_identity(monkeypatch):
    from apix.server import create_app
    from apixis.core.config.core_config import NODE_ID
    from apixis.core.event import EventType, get_event_pipe, subscribe, unsubscribe

    # Exercise the real event runtime without opening unrelated storage services.
    monkeypatch.setattr("apix.server.auto_init.start", AsyncMock())
    monkeypatch.setattr("apix.server.auto_init.stop", AsyncMock())
    app = create_app()
    for _ in range(2):
        received = asyncio.Event()

        @subscribe("apix.migration.health")
        async def receive(event):
            received.set()

        try:
            async with app.router.lifespan_context(app):
                await get_event_pipe().post_event(
                    event_type=EventType.WORKFLOW, event_name="apix.migration.health"
                )
                await asyncio.wait_for(received.wait(), 1)
                async with AsyncClient(
                    transport=ASGITransport(app), base_url="http://test"
                ) as client:
                    response = await client.get("/health")
                assert response.json() == {"status": "ok", "service": NODE_ID}
        finally:
            unsubscribe("receive")


async def test_add_tools_forwards_llm_binding_with_custom_messages_key(closed_scopes):
    class CustomState(TypedDict, total=False):
        conversation: Annotated[list, AutoMerge()]
        observed: str

    def hello():
        return "hello"

    def model(state):
        assert len(state["conversation"]) == 2
        return {"observed": state["conversation"][-1].content}

    graph = (
        AgentGraphCreator(CustomState, messages_key="conversation")
        .add_tools([hello], bind_llm_node="model")
        .add_node(model)
        .compile_agent("tools")
    )
    result = await graph.invoke(
        {
            "conversation": [
                ApixAiMessage(
                    tool_calls=[
                        {"call_id": "hello-1", "tool_name": "hello", "args": {}}
                    ]
                )
            ]
        }
    )
    assert result["observed"] == "hello"
