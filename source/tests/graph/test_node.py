"""Unit tests for graph node result normalisation."""

from dataclasses import is_dataclass

import pytest

from apix.common.type import InvalidNodeReturns
from apix.core.graph import Command, Node


def test_node_requires_a_function():
    """A node cannot be constructed without an executable function."""
    with pytest.raises(ValueError, match="requires a callable function"):
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
async def test_node_preserves_an_ordered_command_list():
    """A node may return several commands for sequential graph application."""
    commands = [
        Command(update={"value": 1}),
        Command(update={"value": 2}, goto="next"),
    ]
    node = Node(lambda state: commands, "multi_command")

    assert await node.execute({}) == commands


def test_command_is_a_dataclass_with_independent_update_defaults():
    """Commands have an unambiguous runtime type and no shared update state."""
    first = Command()
    second = Command()

    first.update["value"] = 1

    assert is_dataclass(Command)
    assert first.update == {"value": 1}
    assert second.update == {}
    assert first.has_goto is False
    assert Command(goto=None).has_goto is True


def test_is_command_requires_an_actual_command_instance():
    """Command-looking dictionaries are not mistaken for Commands."""
    assert Node._is_command(Command()) is True
    assert Node._is_command({"update": {}, "goto": None}) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            {"update": {"value": 2}},
            Command(update={"update": {"value": 2}}),
        ),
        (
            {"update": {"value": 2}, "goto": "next"},
            Command(
                update={
                    "update": {"value": 2},
                    "goto": "next",
                }
            ),
        ),
        ({"goto": None}, Command(update={"goto": None})),
    ],
)
async def test_command_looking_mappings_are_state_updates(result, expected):
    """Only Command instances receive command routing semantics."""
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
    node = Node(
        lambda state: Command(update=[]),
        "invalid_update",
    )

    with pytest.raises(InvalidNodeReturns, match="Command.update must be a dict"):
        await node.execute({})


@pytest.mark.asyncio
async def test_node_rejects_non_string_command_goto():
    """Command.goto accepts only node names or None."""
    node = Node(lambda state: Command(goto=1), "invalid_goto")

    with pytest.raises(InvalidNodeReturns, match="Command.goto must be a string or None"):
        await node.execute({})
