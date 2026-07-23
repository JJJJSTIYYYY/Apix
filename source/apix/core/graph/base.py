"""Shared types and predefined node names for graph execution."""

from collections.abc import Awaitable, Callable
from typing import Any, NotRequired, TypedDict
from dataclasses import dataclass

from apix.common.type.exception import CommandMergeError


@dataclass(frozen=True, slots=True)
class AutoIncrease:
    """Mark an Annotated argument as auto increase.

    This class contains no runtime data. It is only metadata inspected by
    the :class:`NodeGraph` class when a Command update is returned by a :class:`Node`.

    A key in state marked by :class:`AutoIncrease` will execute state[AutoIncreaseKey].__add__(step)
    """

    pass


START = "__start__"
"""Predefined node name that begins every graph invocation."""

END = "__end__"
"""Predefined node name that completes every graph invocation."""

NodeFunction = Callable[[dict], dict] | Callable[[dict], Awaitable[dict]]
"""A synchronous or asynchronous callable that receives graph state."""


class Command(TypedDict):
    """A node result that updates state and optionally chooses the next node.

    Attributes:
        update:
            Values merged into the state carried by the next event.
        goto:
            The next node name. ``None`` explicitly routes to ``END``;
            omitting this key permits a manager-defined default transition.
    """

    update: NotRequired[dict[str, Any]]
    goto: NotRequired[str | None]


def merge_commands(commands: list[Command]) -> Command:
    """Merge multiple commands into one command.

    Merge rules:
        - ``update`` values are merged from left to right.
        - Later update values overwrite earlier values with the same key.
        - An omitted ``goto`` does not participate in route selection.
        - Explicit ``goto=None`` participates in route selection and means END.
        - All explicitly specified ``goto`` values must be equal.

    Args:
        commands:
            Commands to merge.

    Returns:
        The merged command.

    Raises:
        TypeError:
            If ``commands`` or an ``update`` value has an invalid type.
        CommandMergeError:
            If commands specify different ``goto`` values.
    """
    if not isinstance(commands, list):
        raise TypeError(
            f"`commands` must be a list, got {type(commands).__name__}."
        )

    merged_update: dict[str, Any] = {}

    has_update = False
    has_goto = False
    merged_goto: str | None = None

    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            raise TypeError(
                f"commands[{index}] must be a Command-compatible dict, "
                f"got {type(command).__name__}."
            )

        if "update" in command:
            update = command["update"]

            if not isinstance(update, dict):
                raise TypeError(
                    f"commands[{index}]['update'] must be a dict, "
                    f"got {type(update).__name__}."
                )

            merged_update.update(update)
            has_update = True
            
        if "goto" in command:
            goto = command["goto"]

            if goto is not None and not isinstance(goto, str):
                raise TypeError(
                    f"commands[{index}]['goto'] must be str or None, "
                    f"got {type(goto).__name__}."
                )

            if not has_goto:
                merged_goto = goto
                has_goto = True
            elif goto != merged_goto:
                raise CommandMergeError(
                    "Cannot merge commands with different `goto` values: "
                    f"{merged_goto!r} and {goto!r}."
                )

    result: Command = {}

    if has_update:
        result["update"] = merged_update

    if has_goto:
        result["goto"] = merged_goto

    return result