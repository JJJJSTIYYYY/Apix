import functools
import inspect
from collections.abc import Awaitable, Callable, Mapping

from apix.common.type.exception import InvalidNodeReturns
from apix.core.graph.base import Command, NodeFunction


class Node:
    """A named graph node that normalises synchronous and asynchronous callables."""

    def __init__(self, func: NodeFunction, name: str | None = None):
        """Create a node.

        Args:
            func: Callable invoked with a copy of the current graph state.
            name: Unique node name. Defaults to ``func.__name__``.

        Raises:
            ValueError: If no callable or usable name is supplied.
        """
        if func is None:
            raise ValueError("A graph node requires a function.")
        
        self.name = name or func.__name__
        if not self.name:
            raise ValueError("A graph node requires a name.")
        
        self.func = self._wrap_func(func)


    async def execute(self, state: dict) -> Command:
        """Execute the wrapped callable and return its normalised command.

        Args:
            state: State snapshot supplied to the node callable.

        Returns:
            The command produced from the callable's return value.
        """
        return await self.func(state)
    

    @staticmethod
    def _normalise_result(result: object) -> Command:
        """Convert a node return value into a :class:`Command`.

        A regular mapping is treated as a state update. A mapping containing
        ``goto``, or one using only the ``update``/``goto`` command keys, is
        treated as a command.

        Raises:
            InvalidNodeReturns: If the value cannot represent a valid command.
        """
        if not isinstance(result, Mapping):
            raise InvalidNodeReturns("Node functions must return a dict or Command, " f"got {type(result).__name__}.")
        
        # TypedDict values are ordinary dicts at runtime. ``goto`` therefore
        # distinguishes a Command from a normal state-update dictionary.
        command_keys = {"update", "goto"}
        if "goto" in result or (set(result).issubset(command_keys) and "update" in result and isinstance(result["update"], Mapping)):
            update = result.get("update", {})
            goto = result.get("goto")
            if not isinstance(update, Mapping):
                raise InvalidNodeReturns("Command.update must be a dict.")
            if goto is not None and not isinstance(goto, str):
                raise InvalidNodeReturns("Command.goto must be a string or None.")
            command = Command(update=dict(update))
            if "goto" in result:
                command["goto"] = goto
            return command
        return Command(update=dict(result))
    

    def _wrap_func(self, func: NodeFunction) -> Callable[[dict], Awaitable[Command]]:
        """Wrap ``func`` so sync and async callables share one async interface."""
        @functools.wraps(func)
        async def wrapped(state: dict) -> Command:
            """Invoke the original callable and normalise its returned value."""
            result = func(state)
            if inspect.isawaitable(result):
                result = await result
            return self._normalise_result(result)
        return wrapped
