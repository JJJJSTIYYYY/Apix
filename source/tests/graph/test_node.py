"""Unit tests for graph node result normalisation."""

import pytest

from apix.common.type.exception import InvalidNodeReturns
from apix.core.graph import Command, Node


def test_node_requires_a_function():
    """A node cannot be constructed without an executable function."""
    with pytest.raises(ValueError, match="requires a function"):
        Node(None)


def test_node_requires_a_usable_name():
    """An unnamed callable must be given an explicit node name."""
    def unnamed(state):
        return state

    unnamed.__name__ = ""

    with pytest.raises(ValueError, match="requires a name"):
        Node(unnamed)


@pytest.mark.asyncio
async def test_sync_node_mapping_becomes_state_update():
    """A regular mapping is normalised to Command.update."""
    node = Node(lambda state: {"number": state["number"] + 1}, "increment")

    assert await node.execute({"number": 1}) == Command(update={"number": 2})


@pytest.mark.asyncio
async def test_async_node_is_awaited_and_normalised():
    """Async node callables share the same result contract as sync callables."""
    async def increment(state):
        return {"number": state["number"] + 1}

    node = Node(increment)

    assert await node.execute({"number": 1}) == Command(update={"number": 2})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"update": {"value": 2}}, Command(update={"value": 2})),
        (
            {"update": {"value": 2}, "goto": "next"},
            Command(update={"value": 2}, goto="next"),
        ),
        ({"goto": None}, Command(update={}, goto=None)),
    ],
)
async def test_command_mappings_are_preserved(result, expected):
    """Command-shaped mappings retain their update and goto semantics."""
    node = Node(lambda state: result, "command_node")

    assert await node.execute({}) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [None, 1, ["not", "a", "mapping"]])
async def test_node_rejects_non_mapping_results(result):
    """Every node result must be representable as a mapping command."""
    node = Node(lambda state: result, "invalid_node")

    with pytest.raises(InvalidNodeReturns, match="must return a dict or Command"):
        await node.execute({})


@pytest.mark.asyncio
async def test_node_rejects_non_mapping_command_update():
    """Command.update must itself be a mapping."""
    node = Node(lambda state: {"update": [], "goto": "next"}, "invalid_update")

    with pytest.raises(InvalidNodeReturns, match="Command.update must be a dict"):
        await node.execute({})


@pytest.mark.asyncio
async def test_node_rejects_non_string_command_goto():
    """Command.goto accepts only node names or None."""
    node = Node(lambda state: {"update": {}, "goto": 1}, "invalid_goto")

    with pytest.raises(InvalidNodeReturns, match="Command.goto must be a string or None"):
        await node.execute({})
