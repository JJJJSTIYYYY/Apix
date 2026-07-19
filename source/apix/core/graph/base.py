"""Shared types and predefined node names for graph execution."""

from collections.abc import Awaitable, Callable
from typing import NotRequired, TypedDict


START = "__start__"
"""Predefined node name that begins every graph invocation."""

END = "__end__"
"""Predefined node name that completes every graph invocation."""

NodeFunction = Callable[[dict], dict] | Callable[[dict], Awaitable[dict]]
"""A synchronous or asynchronous callable that receives graph state."""


class Command(TypedDict):
    """A node result that updates state and optionally chooses the next node.

    Attributes:
        update: Values merged into the state carried by the next event.
        goto: The next node name. ``None`` explicitly routes to :data:`END`;
            omitting this key permits a manager-defined default transition.
    """

    update: NotRequired[dict]
    goto: NotRequired[str | None]
