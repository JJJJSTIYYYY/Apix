import asyncio
import functools
import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeGuard, TypeVar

from apix.core.utils.exception import InvalidNodeReturnsError
from apix.core.graph.base import Command, NodeFunction


_TaskResult = TypeVar("_TaskResult")


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
            InvalidNodeReturnsError: If the value cannot represent a valid command.
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
                raise InvalidNodeReturnsError("Command.update must be a dict.")
            if goto is not None and not isinstance(goto, str):
                raise InvalidNodeReturnsError(
                    "Command.goto must be a string or None."
                )

            return Command(update=dict(update), goto=goto)

        if not isinstance(result, Mapping):
            raise InvalidNodeReturnsError(
                "Node functions must return a dict or Command, or "
                f"list[Command], got {type(result).__name__}."
            )

        return Command(update=dict(result))

    @staticmethod
    async def _gather_tasks_in_order(
        tasks: list[asyncio.Task[_TaskResult]],
    ) -> list[_TaskResult]:
        """Wait for concurrent tasks and preserve their declaration order.

        ``asyncio.gather`` returns results in the order of its input tasks,
        independently of completion order. If one task fails or the caller is
        cancelled, every unfinished sibling is cancelled and awaited before
        the original exception is propagated.
        """
        try:
            return list(await asyncio.gather(*tasks))
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )
            raise
    

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

    A regular node contains exactly one node function.
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
            raise InvalidNodeReturnsError(
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


class ParallelNode(BaseNode):
    """Execute multiple node functions concurrently and join their commands.

    Every branch receives the same node-local state snapshot. Branch functions
    should therefore treat state as read-only and communicate changes through
    their returned mapping or :class:`Command`. Results are returned in branch
    declaration order so :class:`NodeGraph` can apply them deterministically,
    regardless of the order in which branches finish.
    """

    name: str
    func: tuple[Callable[[dict], Awaitable[Command]], ...]

    def __init__(
        self,
        funcs: list[NodeFunction] | tuple[NodeFunction, ...],
        name: str = "parallel",
    ) -> None:
        """Create a concurrent collection of regular node functions.

        Args:
            funcs: Non-empty list or tuple of synchronous or asynchronous node
                functions. Each function must return one mapping or Command.
            name: Unique graph node name.

        Raises:
            TypeError: If ``funcs`` is not a list or tuple.
            ValueError: If the name is empty, no branch is supplied, or a
                branch is not callable.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("A parallel graph node requires a name.")
        if not isinstance(funcs, (list, tuple)):
            raise TypeError("Parallel node functions must be a list or tuple.")
        if not funcs:
            raise ValueError(
                "A parallel graph node requires at least one function."
            )
        if any(not callable(func) for func in funcs):
            raise ValueError("Every parallel graph node branch must be callable.")

        self.name = name
        self.func = tuple(
            self._wrap_func(func)
            for func in funcs
        )

    @staticmethod
    def _normalise_result(
        result: object,
    ) -> Command:
        """Normalise one branch result without allowing nested command lists."""
        if isinstance(result, list):
            raise InvalidNodeReturnsError(
                "Parallel node branch functions must return a dict or Command, "
                "not list[Command]."
            )
        return BaseNode._normalise_single_result(result)

    async def execute(
        self,
        state: dict,
    ) -> list[Command]:
        """Execute every branch concurrently and return commands in input order."""
        if not isinstance(state, dict):
            raise TypeError("Graph state must be a dict.")

        tasks = [
            asyncio.create_task(
                branch(state),
                name=(
                    f"graph-node-{self.name}-branch-{index}-"
                    f"{getattr(branch, '__name__', 'anonymous')}"
                ),
            )
            for index, branch in enumerate(self.func)
        ]
        return await self._gather_tasks_in_order(tasks)
