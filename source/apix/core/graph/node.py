import functools
import inspect
from collections.abc import Awaitable, Callable, Mapping
from abc import ABC, abstractmethod
from typing import Any, TypeGuard

from apix.common.type.exception import InvalidNodeReturns
from apix.core.graph.base import Command, NodeFunction


class BaseNode(ABC):

    name: str
    func: Any

    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    async def execute(
        self,
        state: dict,
    ) -> Command | list[Command]:
        pass

    @staticmethod
    def _is_command(value: Any) -> TypeGuard[Command]:
        """Return whether a dictionary has the runtime shape of Command."""
        if not isinstance(value, dict):
            return False

        if not set(value).issubset({"update", "goto"}):
            return False

        if (
            "update" in value
            and not isinstance(value["update"], dict)
        ):
            return False

        if (
            "goto" in value
            and value["goto"] is not None
            and not isinstance(value["goto"], str)
        ):
            return False

        return True
    
    @staticmethod
    def _normalise_result(
        result: object,
    ) -> Command | list[Command]:
        """Convert a node return value into one or more commands.

        A regular mapping is treated as a state update. A mapping containing
        ``goto``, or one using only the ``update``/``goto`` command keys, is
        treated as a command. Lists are normalised item by item and preserve
        their original order.

        Raises:
            InvalidNodeReturns: If the value cannot represent a valid command.
        """
        if isinstance(result, list):
            return [
                BaseNode._normalise_single_result(item)
                for item in result
            ]

        return BaseNode._normalise_single_result(result)

    @staticmethod
    def _normalise_single_result(result: object) -> Command:
        """Convert one node return value into a :class:`Command`."""
        if not isinstance(result, Mapping):
            raise InvalidNodeReturns(
                "Node functions must return a dict or Command, or "
                f"list[Command], got {type(result).__name__}."
            )
        
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
    

    def _wrap_func(
        self,
        func: NodeFunction,
    ) -> Callable[
        [dict],
        Awaitable[Command | list[Command]],
    ]:
        """Wrap ``func`` so sync and async callables share one async interface.
        The wrapped function returns one command or an ordered command list.
        """
        @functools.wraps(func)
        async def wrapped(
            state: dict,
        ) -> Command | list[Command]:
            """Invoke the original callable and normalise its returned value."""
            result = func(state)
            if inspect.isawaitable(result):
                result = await result
            return self._normalise_result(result)
        return wrapped


class Node(BaseNode):
    """A named graph node that normalises synchronous and asynchronous callables.
    A node should only contains a node function.
    """

    name: str
    func: NodeFunction

    def __init__(self, func: NodeFunction, name: str | None = None):
        """Create a node.

        Args:
            func: Callable invoked with a copy of the current graph state.
            name: Unique node name. Defaults to ``func.__name__``.

        Raises:
            ValueError: If no callable or usable name is supplied.
        """
        if func is None or not isinstance(func, Callable):
            raise ValueError("A graph node requires a callable function.")
        
        self.name = name or func.__name__
        if not self.name:
            raise ValueError("A graph node requires a name.")
        
        self.func = self._wrap_func(func)


    async def execute(
        self,
        state: dict,
    ) -> Command | list[Command]:
        """Execute the callable and return its normalised command result.

        Args:
            state: State snapshot supplied to the node callable.

        Returns:
            One command or an ordered list of commands.
        """
        return await self.func(state)
