"""Focused unit tests for NodeGraph defensive runtime behaviour."""

import asyncio

import pytest

from apix.core.graph import END, START, NodeGraph


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
        graph.apply_command({"update": []}, START, _graph_context())


def test_apply_command_rejects_non_string_goto():
    """A direct apply_command call cannot route to a non-string target."""
    graph = NodeGraph({}, {START: END})

    with pytest.raises(TypeError, match="Command.goto must be a string or None"):
        graph.apply_command({"goto": 1}, START, _graph_context())


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
