"""Tests for agent tool wrapping and ToolNode execution."""

import asyncio

import pytest

from apix.agent.sdk.tool import Tool, ToolNode, tool
from apix.agent.sdk.utils.message import (
    ApixAiMessage,
    ApixToolMessage,
)
from apix.core.graph import Command, GraphManager


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


def _state_with_calls(*calls: dict) -> dict:
    return {
        "messages": [
            ApixAiMessage(tool_calls=list(calls)),
        ]
    }


def _message_from(command: Command) -> ApixToolMessage:
    messages = command["update"]["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 1
    message = messages[0]
    assert isinstance(message, ApixToolMessage)
    return message


def test_tool_decorator_preserves_function_name_and_metadata():
    """Both decorator forms create named Tool objects."""
    @tool
    def direct(value: int) -> str:
        """Direct tool."""
        return str(value)

    @tool(description="Custom description")
    def configured(value: int) -> str:
        return str(value)

    assert isinstance(direct, Tool)
    assert direct.name == "direct"
    assert direct.__name__ == "direct"
    assert direct.func.__name__ == "direct"
    assert direct.__doc__ == "Direct tool."

    assert isinstance(configured, Tool)
    assert configured.name == "configured"
    assert configured.description == "Custom description"


@pytest.mark.asyncio
async def test_tool_node_executes_concurrently_but_returns_call_order():
    """A later tool can finish first without reordering its command."""
    second_started = asyncio.Event()
    completion_order = []

    @tool
    async def first(value: str) -> str:
        await second_started.wait()
        await asyncio.sleep(0.01)
        completion_order.append("first")
        return f"first:{value}"

    @tool
    async def second(value: str) -> str:
        second_started.set()
        completion_order.append("second")
        return f"second:{value}"

    node = ToolNode([first, second])
    commands = await asyncio.wait_for(
        node.execute(
            _state_with_calls(
                _tool_call("first", "call-1", {"value": "a"}),
                _tool_call("second", "call-2", {"value": "b"}),
            )
        ),
        timeout=1,
    )

    assert completion_order == ["second", "first"]
    assert len(commands) == 2
    assert [
        _message_from(command).content
        for command in commands
    ] == ["first:a", "second:b"]
    assert [
        _message_from(command).tool_call_id
        for command in commands
    ] == ["call-1", "call-2"]


@pytest.mark.asyncio
async def test_plain_dict_result_is_stringified_into_tool_message():
    """A dict that is not Command-shaped is normal tool output."""
    def payload() -> dict:
        return {"answer": 42}

    node = ToolNode(payload)
    commands = await node.execute(
        _state_with_calls(
            _tool_call("payload", "call-payload"),
        )
    )

    message = _message_from(commands[0])
    assert message.content == "{'answer': 42}"
    assert message.name == "payload"
    assert message.tool_call_id == "call-payload"


@pytest.mark.asyncio
async def test_command_result_is_preserved_and_string_message_is_converted():
    """Command routing and updates survive ToolNode normalisation."""
    @tool
    def update_state() -> Command:
        return Command(
            update={
                "messages": "finished",
                "value": 3,
            },
            goto="next",
        )

    node = ToolNode(update_state)
    commands = await node.execute(
        _state_with_calls(
            _tool_call("update_state", "call-update"),
        )
    )

    assert len(commands) == 1
    assert commands[0]["goto"] == "next"
    assert commands[0]["update"]["value"] == 3
    message = _message_from(commands[0])
    assert message.content == "finished"
    assert message.tool_call_id == "call-update"


@pytest.mark.asyncio
async def test_invalid_command_shape_is_stringified():
    """A dict with invalid Command field types is ordinary output."""
    def invalid_shape() -> dict:
        return {"update": []}

    node = ToolNode(invalid_shape)
    commands = await node.execute(
        _state_with_calls(
            _tool_call("invalid_shape", "call-invalid"),
        )
    )

    assert _message_from(commands[0]).content == "{'update': []}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [
        {},
        {"messages": []},
        {"messages": [ApixToolMessage(content="old", tool_call_id="old")]},
        {"messages": [ApixAiMessage()]},
    ],
)
async def test_tool_node_without_pending_calls_returns_empty_command_list(
    state,
):
    """No pending tool call means no per-tool command is produced."""
    node = ToolNode(lambda: "unused")

    assert await node.execute(state) == []


@pytest.mark.asyncio
async def test_tool_node_rejects_unknown_tool_before_execution():
    """Every model-selected tool must be registered on the node."""
    node = ToolNode(lambda: "unused")

    with pytest.raises(ValueError, match="not registered"):
        await node.execute(
            _state_with_calls(
                _tool_call("missing", "call-missing"),
            )
        )


def test_graph_manager_accepts_tool_node_as_base_node():
    """ToolNode is registered directly instead of being wrapped as a callable."""
    node = ToolNode(lambda: "unused")
    manager = GraphManager().add_node(node)

    assert manager._nodes[node.name] is node
