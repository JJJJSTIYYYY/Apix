"""Shared types and predefined node names for graph execution."""

from collections.abc import Awaitable, Callable
from typing import (
    Annotated,
    Any,
    NotRequired,
    TypedDict,
    get_args,
    get_origin,
    get_type_hints,
)
from dataclasses import dataclass

from apix.common.type.exception import CommandMergeError


@dataclass(frozen=True, slots=True)
class AutoIncrease:
    """Mark an ``Annotated`` state field as auto-increasing.

    This class contains no runtime data. It is only metadata inspected by
    :class:`NodeGraph` when a :class:`Command` update is applied.

    When an existing marked field is updated, the graph calls the current
    value's ``__add__`` method with the update value. A field that is not yet
    present in state is initialized directly from the update value.

    Example:
        ``messages: Annotated[list, AutoIncrease()]``
    """

    pass


@dataclass(frozen=True, slots=True)
class Replace:
    """Explicitly replace a state field during a command update.

    ``Replace`` is primarily used to bypass :class:`AutoIncrease` for one
    update. The graph unwraps it before storing the value, so the wrapper never
    becomes part of the resulting state.

    Example:
        ``Command(update={"messages": Replace([])})``
    """

    value: Any


def get_auto_increase_keys(
    state_schema: type | None,
) -> frozenset[str]:
    """Return fields marked with :class:`AutoIncrease` in a state schema.

    ``state_schema`` is normally a ``TypedDict`` class. Regular annotated
    classes are also accepted because only their resolved type hints are
    inspected.

    Both ``AutoIncrease`` and ``AutoIncrease()`` metadata forms are supported.

    Args:
        state_schema:
            State schema whose ``Annotated`` metadata should be inspected.
            ``None`` disables auto-increasing updates.

    Raises:
        TypeError:
            If ``state_schema`` is not a class.
        NameError:
            If the schema contains an unresolved forward reference.
    """
    if state_schema is None:
        return frozenset()

    if not isinstance(state_schema, type):
        raise TypeError(
            "`state_schema` must be a class or None, "
            f"got {type(state_schema).__name__}."
        )

    type_hints = get_type_hints(
        state_schema,
        include_extras=True,
    )

    return frozenset(
        key
        for key, annotation in type_hints.items()
        if (
            get_origin(annotation) is Annotated
            and any(
                marker is AutoIncrease
                or isinstance(marker, AutoIncrease)
                for marker in get_args(annotation)[1:]
            )
        )
    )


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
            Wrapping a value in :class:`Replace` explicitly replaces that
            field even when its state annotation contains
            :class:`AutoIncrease`.
        goto:
            The next node name. ``None`` explicitly routes to ``END``;
            omitting this key permits a manager-defined default transition.
    """

    update: NotRequired[dict[str, Any]]
    goto: NotRequired[str | None]