"""Shared types and predefined node names for graph execution."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Annotated,
    Any,
    TypeAlias,
    get_args,
    get_origin,
    get_type_hints,
)


@dataclass(frozen=True, slots=True)
class AutoMerge:
    """Mark an ``Annotated`` state field as auto-increasing.

    This class contains no runtime data. It is only metadata inspected by
    :class:`NodeGraph` when a :class:`Command` update is applied.

    When an existing marked field is updated, the graph calls the current
    value's ``__add__`` method with the update value. A field that is not yet
    present in state is initialized directly from the update value.

    Example:
        ``messages: Annotated[list, AutoMerge()]``
    """

    pass


@dataclass(frozen=True, slots=True)
class KeepRef:
    """Mark an ``Annotated`` state field to keep its reference during copying.

    This class contains no runtime data. It is only metadata inspected by
    :class:`NodeGraph` when a state copy operation is performed.

    When a marked field is copied, the graph keeps the original field value's
    reference instead of creating a copied object. Other state fields continue
    to follow the normal copy behavior.

    This is useful for fields that represent shared runtime resources or
    mutable objects that should remain synchronized across copied states.

    Example:
        ``context: Annotated[ContextOrganizer, KeepRef()]``
    """

    pass


@dataclass(frozen=True, slots=True)
class Reset:
    """Explicitly replace a state field during a command update.

    ``Reset`` is primarily used to bypass :class:`AutoMerge` for one
    update. The graph unwraps it before storing the value, so the wrapper never
    becomes part of the resulting state.

    Example:
        ``Command(update={"messages": Reset([])})``
    """

    value: Any


def get_auto_increase_keys(
    state_schema: type | None,
) -> frozenset[str]:
    """Return fields marked with :class:`AutoMerge` in a state schema.

    ``state_schema`` is normally a ``TypedDict`` class. Regular annotated
    classes are also accepted because only their resolved type hints are
    inspected.

    Both ``AutoMerge`` and ``AutoMerge()`` metadata forms are supported.

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
                marker is AutoMerge
                or isinstance(marker, AutoMerge)
                for marker in get_args(annotation)[1:]
            )
        )
    )


def get_keep_ref_keys(
    state_schema: type | None,
) -> frozenset[str]:
    """Return fields marked with :class:`KeepRef` in a state schema.

    ``state_schema`` is normally a ``TypedDict`` class. Regular annotated
    classes are also accepted because only their resolved type hints are
    inspected.

    Both ``KeepRef`` and ``KeepRef()`` metadata forms are supported.

    Args:
        state_schema:
            State schema whose ``Annotated`` metadata should be inspected.
            ``None`` returns an empty set.

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
                marker is KeepRef
                or isinstance(marker, KeepRef)
                for marker in get_args(annotation)[1:]
            )
        )
    )


START = "__start__"
"""Predefined node name that begins every graph invocation."""

END = "__end__"
"""Predefined node name that completes every graph invocation."""


class _UnsetGoto(Enum):
    """Sentinel used to distinguish an omitted route from ``goto=None``."""

    VALUE = "unset"


_UNSET_GOTO = _UnsetGoto.VALUE


@dataclass(slots=True)
class Command:
    """A node result that updates state and optionally chooses the next node.

    Attributes:
        update:
            Values merged into the state carried by the next event.
            Wrapping a value in :class:`Reset` explicitly replaces that
            field even when its state annotation contains
            :class:`AutoMerge`.
        goto:
            The next node name. ``None`` explicitly routes to ``END``;
            omitting this key permits a manager-defined default transition.
    """

    update: dict[str, Any] = field(default_factory=dict)
    goto: str | None | _UnsetGoto = _UNSET_GOTO

    @property
    def has_goto(self) -> bool:
        """Return whether ``goto`` was explicitly supplied."""
        return self.goto is not _UNSET_GOTO


NodeResult: TypeAlias = dict[str, Any] | Command | list[Command]
"""A state update, one command, or an ordered list of commands."""

NodeFunction: TypeAlias = (
    Callable[[dict[str, Any]], NodeResult]
    | Callable[[dict[str, Any]], Awaitable[NodeResult]]
)
"""A synchronous or asynchronous callable that receives graph state."""
