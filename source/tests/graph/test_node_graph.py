"""Focused unit tests for NodeGraph defensive runtime behaviour."""

import asyncio
from typing import Annotated, TypedDict

import pytest

from apix.core.graph import (
    AutoMerge,
    Command,
    END,
    START,
    NodeGraph,
    Reset,
)


def _graph_context(state=None):
    """Build the minimal context required by apply_command."""
    return {
        "state": state or {},
        "steps": 0,
    }


def test_apply_command_rejects_non_dict_update():
    """NodeGraph defensively validates commands from external callers."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="Command.update must be a dict"):
        graph.apply_command(Command(update=[]), START, _graph_context())


def test_apply_command_rejects_non_string_goto():
    """A direct apply_command call cannot route to a non-string target."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="Command.goto must be a string or None"):
        graph.apply_command(Command(goto=1), START, _graph_context())


def test_apply_command_rejects_plain_dict():
    """Only Command instances satisfy the direct runtime contract."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="must return a Command"):
        graph.apply_command({}, START, _graph_context())


class AutoMergeState(TypedDict):
    """State schema used to exercise annotated update behaviour."""

    values: Annotated[list[int], AutoMerge()]
    total: Annotated[int, AutoMerge]
    replaced: list[int]


def test_apply_command_auto_increases_annotated_fields():
    """Marked existing fields call __add__; unmarked fields are replaced."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )
    context = _graph_context(
        {
            "values": [1],
            "total": 2,
            "replaced": [1],
        }
    )

    state, next_node = graph.apply_command(
        Command(
            update={
                "values": [2, 3],
                "total": 4,
                "replaced": [2],
            }
        ),
        START,
        context,
    )

    assert state == {
        "values": [1, 2, 3],
        "total": 6,
        "replaced": [2],
    }
    assert next_node == END
    assert context["state"] == {
        "values": [1],
        "total": 2,
        "replaced": [1],
    }


def test_apply_command_initializes_missing_auto_increase_field():
    """A marked field without a current value is assigned directly."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )

    state, _ = graph.apply_command(
        Command(update={"values": [1]}),
        START,
        _graph_context(),
    )

    assert state == {"values": [1]}


def test_replace_bypasses_auto_increase_and_is_unwrapped():
    """Reset forces assignment for both marked and ordinary fields."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )
    context = _graph_context(
        {
            "values": [1, 2],
            "replaced": [1, 2],
        }
    )

    state, _ = graph.apply_command(
        Command(
            update={
                "values": Reset([3]),
                "replaced": Reset([4]),
            }
        ),
        START,
        context,
    )

    assert state == {
        "values": [3],
        "replaced": [4],
    }
    assert context["state"] == {
        "values": [1, 2],
        "replaced": [1, 2],
    }


def test_replace_initializes_missing_auto_increase_field():
    """Reset is also unwrapped when the marked field has no old value."""
    graph = NodeGraph(
        {},
        {START: END},
        state_schema=AutoMergeState,
    )

    state, _ = graph.apply_command(
        Command(update={"values": Reset([1])}),
        START,
        _graph_context(),
    )

    assert state == {"values": [1]}


def test_node_graph_rejects_non_class_state_schema():
    """Annotated metadata must come from a schema class."""
    with pytest.raises(
        TypeError,
        match="state_schema.*class or None",
    ):
        NodeGraph(
            {},
            {START: END},
            state_schema={},
        )


@pytest.mark.asyncio
async def test_finish_and_fail_do_not_replace_completed_future():
    """Late END or failure events cannot overwrite an invocation result."""
    completion = asyncio.get_running_loop().create_future()
    completion.set_result({"original": True})
    context = {
        "state": {"replacement": True},
        "completion": completion,
    }

    NodeGraph._finish(context)
    NodeGraph._fail(context, RuntimeError("late failure"))

    assert await completion == {"original": True}
