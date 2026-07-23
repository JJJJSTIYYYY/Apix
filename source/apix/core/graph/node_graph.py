"""Stateless, event-driven graph runtime."""

import asyncio
import copy
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from apix.core.event import ApixEvent, EventType, apix_event_loop, apix_event_registry, event_pipe_writer
from apix.core.graph.base import END, START, Command
from apix.core.graph.node import Node
from apix.core.stream import (
    StreamChannel,
    StreamWriter,
    noop_stream_writer,
    stream_writer_context,
)


class NodeGraph:
    """Execute state-processing nodes by passing state in event contexts.

    The graph does not retain invocation state. Each event context contains the
    current ``state`` and a unique ``run_id``. The run ID identifies which
    registered graph listeners may consume the event, without exposing or
    requiring a graph ID in the context.
    """

    def __init__(
        self,
        nodes: dict[str, Node],
        default_gotos: dict[str, str],
        *,
        max_steps: int = 1024,
    ):
        """Create a compiled graph and register listeners for all node names."""
        self._nodes = dict(nodes)
        self._default_gotos = dict(default_gotos)
        self._max_steps = max_steps
        self._active_runs: set[str] = set()
        self._listener_namespace = uuid.uuid4().hex
        self._register_node_listeners()


    def _register_node_listeners(self) -> None:
        """Subscribe handlers for user nodes plus the predefined start/end nodes."""
        for node_name in (START, *self._nodes, END):
            async def run_node(event: ApixEvent, *, _node_name: str = node_name) -> None:
                """Extract context state and execute the event's graph node."""
                context = event.context
                if not self._is_active_context(context):
                    return
                if _node_name == START:
                    await self._execute_start(context)
                elif _node_name == END:
                    self._finish(context)
                else:
                    await self._execute_node(_node_name, context)

            run_node.__name__ = f"graph_listener_{self._listener_namespace}_{node_name}"
            apix_event_registry.subscribe(node_name)(run_node)


    def _is_active_context(self, context: object) -> bool:
        """Return whether an event context belongs to an active invocation."""
        return (
            isinstance(context, dict)
            and isinstance(context.get("run_id"), str)
            and context["run_id"] in self._active_runs
            and isinstance(context.get("state"), dict)
            and isinstance(context.get("completion"), asyncio.Future)
        )


    async def invoke(self, state: dict) -> dict:
        """Start a graph invocation at :data:`START` and return its final state.

        The input state is deep-copied into the first event context. Independent
        invocations may run concurrently because all evolving state stays in
        their event contexts rather than on this graph object.
        """
        return await self._invoke(state, noop_stream_writer())


    async def stream(self, state: dict) -> AsyncIterator[Any]:
        """Yield custom chunks emitted by nodes during one graph invocation.

        Nodes emit chunks by calling :func:`get_stream_writer` and invoking the
        returned writer. The iterator ends when the graph reaches :data:`END`.
        If graph execution fails, queued chunks are yielded first and then the
        original exception is propagated to the stream consumer.

        Args:
            state: Initial graph state. It is deep-copied before execution.

        Yields:
            Custom chunks in the order in which nodes emitted them.
        """
        channel = StreamChannel()
        execution_task = asyncio.create_task(
            self._invoke(state, channel.writer),
            name=f"graph-stream-{uuid.uuid4().hex}",
        )
        execution_task.add_done_callback(lambda task: channel.close())

        try:
            async for chunk in channel:
                yield chunk
            await execution_task
        finally:
            if not execution_task.done():
                execution_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await execution_task
            channel.close()


    async def _invoke(self, state: dict, stream_writer: StreamWriter) -> dict:
        """Run a graph with the writer assigned to each executing node."""
        if not isinstance(state, dict):
            raise TypeError("Graph state must be a dict.")

        await apix_event_loop.start()
        run_id = "graph-"+uuid.uuid4().hex
        completion = asyncio.get_running_loop().create_future()
        context = {
            "run_id": run_id,
            "state": copy.deepcopy(state),
            "steps": 0,
            "completion": completion,
            "stream_writer": stream_writer,
        }
        self._active_runs.add(run_id)
        try:
            await self._post_next(START, context)
            return await completion
        finally:
            self._active_runs.discard(run_id)


    async def _execute_start(self, context: dict) -> None:
        """Route the predefined start node to its configured successor."""
        try:
            await self._post_next(self._default_gotos[START], context)
        except Exception as exc:
            self._fail(context, exc)


    async def _execute_node(self, node_name: str, context: dict) -> None:
        """Inject context state into one node and emit its next-node event."""
        try:
            writer = context.get("stream_writer", noop_stream_writer())
            with stream_writer_context(writer):
                command = await self._nodes[node_name].execute(
                    copy.deepcopy(context["state"])
                )
            state, next_node = self.apply_command(command, node_name, context)
            next_context = {**context, "state": state, "steps": context["steps"] + 1}
            await self._post_next(next_node, next_context)
        except Exception as exc:
            self._fail(context, exc)


    def apply_command(self, command: Command, node_name: str, context: dict) -> tuple[dict, str]:
        """Return updated state and the target selected by a node command."""
        update = command.get("update", {})
        if not isinstance(update, dict):
            raise TypeError("Command.update must be a dict.")
        steps = context.get("steps", 0) + 1
        if steps > self._max_steps:
            raise RecursionError(f"Graph exceeded its maximum of {self._max_steps} steps.")

        state = copy.deepcopy(context["state"])
        state.update(copy.deepcopy(update))
        next_node = command.get("goto") if "goto" in command else self._default_gotos.get(node_name, END)
        if next_node is None:
            next_node = END
        if not isinstance(next_node, str):
            raise TypeError("Command.goto must be a string or None.")
        return state, next_node


    async def _post_next(self, node_name: str, context: dict) -> None:
        """Post a node-name event while retaining the invocation context."""
        if node_name not in (START, END) and node_name not in self._nodes:
            raise ValueError(f"Unknown graph node `{node_name}`.")
        await event_pipe_writer.post_event(
            event_type=EventType.INFO,
            event_name=node_name,
            context=context,
        )


    @staticmethod
    def _finish(context: dict) -> None:
        """Resolve an invocation with the state carried by its END event."""
        completion = context["completion"]
        if not completion.done():
            completion.set_result(copy.deepcopy(context["state"]))


    @staticmethod
    def _fail(context: dict, error: Exception) -> None:
        """Resolve an invocation with the exception raised by a graph node."""
        completion = context["completion"]
        if not completion.done():
            completion.set_exception(error)
