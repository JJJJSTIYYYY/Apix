"""End-to-end tests for ToolNode inside the compiled graph runtime."""

import asyncio
from typing import Annotated, Any, TypedDict

import pytest
import pytest_asyncio

from apix.agent.sdk.tool import ToolNode, tool
from apix.agent.sdk.utils.message import (
    ApixAiMessage,
    ApixToolMessage,
)
from apix.core.event.event_loop import apix_event_loop
from apix.core.event.event_writer import event_pipe_writer
from apix.core.graph import (
    AutoMerge,
    START,
    Command,
    GraphManager,
    Node,
    NodeGraph,
)


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
    await event_pipe_writer.clear()


class AgentState(TypedDict, total=False):
    """State schema used by the complete agent-tool graph."""

    messages: Annotated[list[Any], AutoMerge()]
    audit: Annotated[list[str], AutoMerge()]
    winner: str
    observed: dict[str, Any]
    route: str


def _tool_call(
    tool_name: str,
    call_id: str,
    args: dict | None = None,
) -> dict:
    return {
        "call_id": call_id,
        "tool_name": tool_name,
        "args": args,
    }


async def test_concurrent_tools_are_applied_in_tool_call_order():
    """GraphManager compiles Node and ToolNode into one ordered state flow."""
    second_started = asyncio.Event()
    completion_order: list[str] = []

    @tool
    async def first(value: str) -> Command:
        await second_started.wait()
        await asyncio.sleep(0.01)
        completion_order.append("first")
        return Command(
            update={
                "messages": [
                    ApixToolMessage(
                        content=f"first:{value}",
                        tool_call_id="placeholder",
                    )
                ],
                "audit": ["first"],
                "winner": "first",
            }
        )

    @tool
    async def second(value: str) -> Command:
        second_started.set()
        completion_order.append("second")
        return Command(
            update={
                "messages": [
                    ApixToolMessage(
                        content=f"second:{value}",
                        tool_call_id="placeholder",
                    )
                ],
                "audit": ["second"],
                "winner": "second",
            }
        )

    def emit_tool_calls(state: dict) -> Command:
        return Command(
            update={
                "messages": [
                    ApixAiMessage(
                        tool_calls=[
                            _tool_call(
                                "first",
                                "call-first",
                                {"value": "a"},
                            ),
                            _tool_call(
                                "second",
                                "call-second",
                                {"value": "b"},
                            ),
                        ]
                    )
                ]
            }
        )

    def observe(state: dict) -> dict:
        tool_messages = [
            message
            for message in state["messages"]
            if isinstance(message, ApixToolMessage)
        ]
        return {
            "observed": {
                "contents": [
                    message.content
                    for message in tool_messages
                ],
                "call_ids": [
                    message.tool_call_id
                    for message in tool_messages
                ],
                "winner": state["winner"],
            }
        }

    emit_node = Node(emit_tool_calls)
    tool_node = ToolNode([first, second])
    observe_node = Node(observe)

    graph = (
        GraphManager(AgentState)
        .add_nodes([
            emit_node,
            tool_node,
            observe_node,
        ])
        .add_edge(START, emit_node.name)
        .add_edge(emit_node.name, tool_node.name)
        .add_edge(tool_node.name, observe_node.name)
        .compile_graph()
    )

    assert isinstance(graph, NodeGraph)

    result = await asyncio.wait_for(
        graph.invoke(
            {
                "messages": [],
                "audit": [],
                "winner": "initial",
            }
        ),
        timeout=1,
    )

    assert completion_order == ["second", "first"]
    assert result["audit"] == ["first", "second"]
    assert result["winner"] == "second"
    assert result["observed"] == {
        "contents": ["first:a", "second:b"],
        "call_ids": ["call-first", "call-second"],
        "winner": "second",
    }
    assert isinstance(result["messages"][0], ApixAiMessage)
    assert all(
        isinstance(message, ApixToolMessage)
        for message in result["messages"][1:]
    )


async def test_tool_command_goto_overrides_manager_default_edge():
    """A Tool-produced route is honored after ToolNode returns its list."""
    @tool
    def choose_route() -> Command:
        return Command(
            update={
                "messages": [
                    ApixToolMessage(
                        content="selected",
                        tool_call_id="placeholder",
                    )
                ]
            },
            goto="selected",
        )

    def emit_tool_call(state: dict) -> dict:
        return {
            "messages": [
                ApixAiMessage(
                    tool_calls=[
                        _tool_call(
                            "choose_route",
                            "call-route",
                        )
                    ]
                )
            ]
        }

    def fallback(state: dict) -> dict:
        return {"route": "fallback"}

    def selected(state: dict) -> dict:
        return {"route": "selected"}

    tool_node = ToolNode(choose_route)
    graph = (
        GraphManager(AgentState)
        .add_nodes([
            emit_tool_call,
            tool_node,
            fallback,
            selected,
        ])
        .add_edge(START, "emit_tool_call")
        .add_edge("emit_tool_call", tool_node.name)
        .add_edge(tool_node.name, "fallback")
        .compile_graph()
    )

    result = await graph.invoke({"messages": []})

    assert result["route"] == "selected"
    assert isinstance(result["messages"][-1], ApixToolMessage)
    assert result["messages"][-1].content == "selected"


async def test_empty_tool_call_list_continues_along_default_edge():
    """ToolNode's empty Command list acts as a graph no-op."""
    def emit_without_tool_calls(state: dict) -> dict:
        return {
            "messages": [
                ApixAiMessage(tool_calls=[]),
            ]
        }

    def unused_tool() -> str:
        raise AssertionError("unused tool must not execute")

    def after_tools(state: dict) -> dict:
        return {"route": "after-tools"}

    tool_node = ToolNode(unused_tool)
    graph = (
        GraphManager(AgentState)
        .add_nodes([
            emit_without_tool_calls,
            tool_node,
            after_tools,
        ])
        .add_edge(START, "emit_without_tool_calls")
        .add_edge("emit_without_tool_calls", tool_node.name)
        .add_edge(tool_node.name, "after_tools")
        .compile_graph()
    )

    result = await graph.invoke({"messages": []})

    assert result["route"] == "after-tools"
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], ApixAiMessage)


async def test_tool_exception_propagates_and_stops_downstream_node():
    """Tool failures complete NodeGraph.invoke with the original exception."""
    downstream_calls: list[str] = []

    @tool
    async def explode() -> str:
        await asyncio.sleep(0)
        raise RuntimeError("tool exploded")

    def emit_tool_call(state: dict) -> dict:
        return {
            "messages": [
                ApixAiMessage(
                    tool_calls=[
                        _tool_call(
                            "explode",
                            "call-explode",
                        )
                    ]
                )
            ]
        }

    def downstream(state: dict) -> dict:
        downstream_calls.append("called")
        return {"route": "downstream"}

    tool_node = ToolNode(explode)
    graph = (
        GraphManager(AgentState)
        .add_nodes([
            emit_tool_call,
            tool_node,
            downstream,
        ])
        .add_edge(START, "emit_tool_call")
        .add_edge("emit_tool_call", tool_node.name)
        .add_edge(tool_node.name, "downstream")
        .compile_graph()
    )

    with pytest.raises(RuntimeError, match="tool exploded"):
        await graph.invoke({"messages": []})

    assert downstream_calls == []


async def test_graph_timeout_cancels_running_tool_node():
    """GraphManager timeout applies to specialised ToolNode execution."""
    cancelled = asyncio.Event()

    @tool
    async def slow_tool() -> str:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    tool_node = ToolNode(slow_tool)
    graph = (
        GraphManager(AgentState)
        .add_node(tool_node, timeout=0.02)
        .add_edge(START, tool_node.name)
        .compile_graph()
    )
    state = {
        "messages": [
            ApixAiMessage(
                tool_calls=[
                    _tool_call("slow_tool", "call-slow")
                ]
            )
        ]
    }

    with pytest.raises(
        TimeoutError,
        match=r"Graph node `tools` timed out after 0.02 seconds",
    ):
        await graph.invoke(state)

    assert cancelled.is_set()
