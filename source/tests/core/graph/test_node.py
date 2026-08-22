"""Unit tests for graph node result normalisation."""

import asyncio
from dataclasses import is_dataclass

import pytest

from apix.core.utils.exception import InvalidNodeReturnsError
from apix.core.graph import BaseNode, Command, Node, ParallelNode


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
async def test_regular_node_rejects_an_ordered_command_list():
    """Only specialised BaseNode implementations may return command lists."""
    commands = [
        Command(update={"value": 1}),
        Command(update={"value": 2}, goto="next"),
    ]
    node = Node(lambda state: commands, "multi_command")

    with pytest.raises(InvalidNodeReturnsError, match="not list\\[Command\\]"):
        await node.execute({})


def test_base_node_helper_preserves_specialised_command_lists():
    """Specialised BaseNode implementations may reuse the list normaliser."""
    assert BaseNode._normalise_result(
        [
            {"value": 1},
            Command(update={"value": 2}),
        ]
    ) == [
        Command(update={"value": 1}),
        Command(update={"value": 2}),
    ]
    assert BaseNode._normalise_result(
        {"value": 3}
    ) == Command(update={"value": 3})


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

    with pytest.raises(InvalidNodeReturnsError, match="must return a dict or Command"):
        await node.execute({})


@pytest.mark.asyncio
async def test_node_rejects_non_mapping_command_update():
    """Command.update must itself be a mapping."""
    node = Node(
        lambda state: Command(update=[]),
        "invalid_update",
    )

    with pytest.raises(InvalidNodeReturnsError, match="Command.update must be a dict"):
        await node.execute({})


@pytest.mark.asyncio
async def test_node_rejects_non_string_command_goto():
    """Command.goto accepts only node names or None."""
    node = Node(lambda state: Command(goto=1), "invalid_goto")

    with pytest.raises(InvalidNodeReturnsError, match="Command.goto must be a string or None"):
        await node.execute({})


@pytest.mark.parametrize(
    ("funcs", "error", "message"),
    [
        (None, TypeError, "must be a list or tuple"),
        ([], ValueError, "at least one function"),
        ([lambda state: {}, None], ValueError, "branch must be callable"),
    ],
)
def test_parallel_node_validates_branch_collection(funcs, error, message):
    """A parallel node requires a concrete non-empty callable collection."""
    with pytest.raises(error, match=message):
        ParallelNode(funcs)


@pytest.mark.parametrize("name", ["", None, 1])
def test_parallel_node_requires_a_non_empty_string_name(name):
    """Parallel nodes use the same explicit graph naming contract."""
    with pytest.raises(ValueError, match="requires a name"):
        ParallelNode([lambda state: {}], name=name)


@pytest.mark.asyncio
async def test_parallel_node_executes_concurrently_and_joins_in_input_order():
    """Completion order does not affect the deterministic command order."""
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    received_states = []

    async def first(state):
        received_states.append(state)
        first_started.set()
        await release_first.wait()
        return {"order": ["first"]}

    async def second(state):
        received_states.append(state)
        await first_started.wait()
        release_first.set()
        return Command(
            update={"order": ["second"]},
            goto="joined",
        )

    node = ParallelNode([first, second], name="parallel_work")
    state = {"input": "shared"}

    result = await asyncio.wait_for(node.execute(state), timeout=1)

    assert result == [
        Command(update={"order": ["first"]}),
        Command(update={"order": ["second"]}, goto="joined"),
    ]
    assert received_states == [state, state]
    assert all(branch_state is state for branch_state in received_states)


@pytest.mark.asyncio
async def test_parallel_node_cancels_and_awaits_siblings_after_failure():
    """A failed branch cannot leave sibling tasks running in the background."""
    sibling_started = asyncio.Event()
    sibling_cancelled = asyncio.Event()

    async def fail_after_sibling_starts(state):
        await sibling_started.wait()
        raise RuntimeError("branch failed")

    async def wait_forever(state):
        sibling_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            sibling_cancelled.set()
            raise

    node = ParallelNode(
        [fail_after_sibling_starts, wait_forever],
        name="failing_parallel_work",
    )

    with pytest.raises(RuntimeError, match="branch failed"):
        await asyncio.wait_for(node.execute({}), timeout=1)

    assert sibling_cancelled.is_set()


@pytest.mark.asyncio
async def test_parallel_node_rejects_nested_command_lists():
    """Each parallel branch contributes exactly one command to the join."""
    node = ParallelNode(
        [lambda state: [Command(), Command()]],
        name="nested_commands",
    )

    with pytest.raises(
        InvalidNodeReturnsError,
        match=r"Parallel node branch functions.*not list\[Command\]",
    ):
        await node.execute({})
