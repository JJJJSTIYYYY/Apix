import functools
import inspect
from collections.abc import Awaitable, Callable, Mapping
from abc import ABC, abstractmethod
from typing import Any, TypeGuard

from apix.common.type import InvalidNodeReturns
from apix.core.graph.base import Command, NodeFunction


class BaseNode(ABC):

    name: str
    func: Any

    def __init__(self, *args, **kwargs):
        pass  # pragma: no cover - abstract compatibility hook

    @abstractmethod
    async def execute(
        self,
        state: dict,
    ) -> Command | list[Command]:
        pass  # pragma: no cover - implemented by concrete nodes

    @staticmethod
    def _is_command(value: Any) -> TypeGuard[Command]:
        """Return whether ``value`` is an actual :class:`Command` instance."""
        return isinstance(value, Command)
    
    @staticmethod
    def _normalise_result(
        result: object,
    ) -> Command | list[Command]:
        """Convert a node return value into one or more commands.

        A regular mapping is always treated as a state update. Only an actual
        :class:`Command` instance may select a route. Lists are normalised item
        by item and preserve their original order.

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
        if BaseNode._is_command(result):
            update = result.update
            goto = result.goto

            if not isinstance(update, Mapping):
                raise InvalidNodeReturns("Command.update must be a dict.")
            if (
                result.has_goto
                and goto is not None
                and not isinstance(goto, str)
            ):
                raise InvalidNodeReturns(
                    "Command.goto must be a string or None."
                )

            if result.has_goto:
                return Command(update=dict(update), goto=goto)
            return Command(update=dict(update))

        if not isinstance(result, Mapping):
            raise InvalidNodeReturns(
                "Node functions must return a dict or Command, or "
                f"list[Command], got {type(result).__name__}."
            )

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


    @staticmethod
    def _normalise_result(
        result: object,
    ) -> Command:
        """Normalise one regular node result.

        Ordered command lists are reserved for specialised ``BaseNode``
        implementations such as ``ToolNode``. A regular callable-backed node
        must return exactly one mapping or :class:`Command`.
        """
        if isinstance(result, list):
            raise InvalidNodeReturns(
                "Regular node functions must return a dict or Command, "
                "not list[Command]."
            )

        return BaseNode._normalise_single_result(result)


    async def execute(
        self,
        state: dict,
    ) -> Command:
        """Execute the callable and return its normalised command result.

        Args:
            state: State snapshot supplied to the node callable.

        Returns:
            Exactly one normalised command.
        """
        return await self.func(state)
