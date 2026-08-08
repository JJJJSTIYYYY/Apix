"""Stateless, event-driven graph runtime."""

import asyncio
import copy
import math
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from apix.core.event import ApixEvent, EventType, apix_event_loop, apix_event_registry, event_pipe_writer
from apix.core.graph.base import (
    END,
    START,
    Command,
    Reset,
    get_auto_merge_keys,
    get_keep_ref_keys
)
from apix.core.graph.context.context_store_manager import _context_store_manager
from apix.core.graph.context.base import GraphContext
from apix.core.graph.context.graph_context_store import GraphContextStore
from apix.core.graph.node import BaseNode
from apix.core.graph.stream import (
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
        nodes: dict[str, BaseNode],
        default_gotos: dict[str, str],
        *,
        node_timeouts: dict[str, float | None] | None = None,
        max_steps: int = 1024,
        state_schema: type | None = None,
    ):
        """Create a compiled graph and register listeners for all node names.

        Args:
            nodes: Nodes keyed by their graph names.
            default_gotos: Manager-defined transitions.
            node_timeouts: Optional per-node execution limits in seconds.
                ``None`` and non-positive values wait indefinitely.
            max_steps: Maximum number of user-node executions in one run.
            state_schema: Optional annotated state schema. Fields marked with
                ``Annotated[..., AutoMerge()]`` are combined through their
                current value's ``__add__`` method when updated.
        """
        self._nodes = dict(nodes)
        self._default_gotos = dict(default_gotos)
        supplied_timeouts = dict(node_timeouts or {})
        unknown_timeout_nodes = supplied_timeouts.keys() - self._nodes.keys()
        if unknown_timeout_nodes:
            unknown_names = ", ".join(sorted(unknown_timeout_nodes))
            raise ValueError(
                "Node timeouts reference unknown nodes: "
                f"{unknown_names}."
            )
        self._node_timeouts = {
            node_name: self.normalise_timeout(
                supplied_timeouts.get(node_name)
            )
            for node_name in self._nodes
        }
        self._max_steps = max_steps
        self._state_schema = state_schema
        self._auto_increase_keys = get_auto_merge_keys(
            state_schema
        )
        self._keep_ref_keys = get_keep_ref_keys(
            state_schema
        )
        self._active_runs: set[str] = set()
        self._active_runs_lock = asyncio.Lock()
        self._listener_namespace = uuid.uuid4().hex
        self._register_node_listeners()


    @staticmethod
    def normalise_timeout(
        timeout: float | None,
    ) -> float | None:
        """Return a validated node timeout or ``None`` for no timeout."""
        if timeout is None:
            return None
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("Node timeout must be a number or None.")

        normalised = float(timeout)
        if not math.isfinite(normalised):
            raise ValueError("Node timeout must be finite.")
        if normalised <= 0:
            return None
        return normalised


    def _copy_state(self, state: dict) -> dict:
        """Deep copy state while preserving references marked with ``KeepRef``.

        Fields marked with ``Annotated[..., KeepRef()]`` keep their original
        object references instead of being deep-copied. Other fields follow the
        normal ``copy.deepcopy`` behavior.
        """
        if not isinstance(state, dict):
            raise TypeError("Graph state must be a dict.")

        if not self._keep_ref_keys:
            return copy.deepcopy(state)

        keep_refs = {
            key: state[key]
            for key in self._keep_ref_keys
            if key in state
        }

        # Exclude kept fields before deepcopy so resource-like values do not
        # need to support copying at all. Rebuild in the original key order;
        # this also keeps normal deepcopy alias semantics among unmarked
        # fields without leaking KeepRef semantics to an unmarked alias.
        copied_values = copy.deepcopy(
            {
                key: value
                for key, value in state.items()
                if key not in keep_refs
            }
        )
        return {
            key: (
                keep_refs[key]
                if key in keep_refs
                else copied_values[key]
            )
            for key in state
        }


    def _register_node_listeners(self) -> None:
        """Subscribe handlers for user nodes plus the predefined start/end nodes."""
        for node_name in (START, *self._nodes, END):
            async def run_node(event: ApixEvent, *, _node_name: str = node_name) -> None:
                """Extract context state and execute the event's graph node."""
                context = event.context
                if not await self._is_active_context(context):
                    return
                if _node_name == START:
                    await self._execute_start(context)
                elif _node_name == END:
                    self._finish(context)
                else:
                    await self._execute_node(_node_name, context)

            run_node.__name__ = f"graph_listener_{self._listener_namespace}_{node_name}"
            apix_event_registry.subscribe(node_name)(run_node)


    async def _is_active_context(self, context: object) -> bool:
        """Return whether an event context belongs to an active invocation."""
        if not (
            isinstance(context, dict)
            and isinstance(context.get("run_id"), str)
            and isinstance(context.get("state"), dict)
            and isinstance(context.get("completion"), asyncio.Future)
        ):
            return False

        async with self._active_runs_lock:
            return context["run_id"] in self._active_runs


    async def invoke(self, state: dict, context_store: GraphContextStore = None) -> dict:
        """Start a graph invocation at :data:`START` and return its final state.

        The input state is deep-copied into the first event context. Independent
        invocations may run concurrently because all evolving state stays in
        their event contexts rather than on this graph object.
        """
        return await self._invoke(state, noop_stream_writer(), context_store)


    async def stream(self, state: dict, context_store: GraphContextStore = None) -> AsyncIterator[Any]:
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
            self._invoke(state, channel.writer, context_store),
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


    async def abort(self, context_store_id: str) -> None:
        """Interrupt a graph invocation by its store ID.

        The graph's :data:`END` node is not executed, so the invocation's
        completion future is resolved with the most recently saved state
        snapshot. Any queued chunks are yielded before a stream ends.

        When this method is called, the graph execution is not interrupted
        immediately. Each node execution is performed against a previously
        saved state snapshot, and the snapshot is updated only after the node
        completes successfully. Therefore, the current node will continue
        running, but the interruption takes effect before the next node starts.
        The :meth:`invoke` and :meth:`stream` interfaces return immediately
        with the state from the snapshot saved before the current node began.

        !!! If a graph invocation has no store, it cannot be aborted.

        Raises:
            ValueError: If the store ID is unknown or its run is not active.
        """
        context_store = _context_store_manager.get_store(context_store_id)
        if not context_store:
            raise ValueError(f"Unknown graph context store ID `{context_store_id}`.")
        run_id = context_store.run_id
        async with self._active_runs_lock:
            if run_id not in self._active_runs:
                raise ValueError(f"Unknown graph run ID `{run_id}`.")
            self._active_runs.discard(run_id)
        self._finish(context_store.graph_context)


    async def _invoke(self, state: dict, stream_writer: StreamWriter, context_store: GraphContextStore = None) -> dict:
        """Run a graph with the writer assigned to each executing node."""
        if not isinstance(state, dict):
            raise TypeError("Graph state must be a dict.")

        await apix_event_loop.start()
        run_id = "graph-"+uuid.uuid4().hex
        completion = asyncio.get_running_loop().create_future()
        context: GraphContext = {
            "run_id": run_id,
            "state": self._copy_state(state),
            "steps": 0,
            "completion": completion,
            "stream_writer": stream_writer,
        }
        if context_store is not None:
            context_store.set_store(run_id, context)
            _context_store_manager.add_store(context_store)
        async with self._active_runs_lock:
            self._active_runs.add(run_id)
        try:
            await self._post_next(START, context)
            return await completion
        finally:
            async with self._active_runs_lock:
                self._active_runs.discard(run_id)


    async def _execute_start(self, context: GraphContext) -> None:
        """Route the predefined start node to its configured successor."""
        try:
            await self._post_next(self._default_gotos[START], context)
        except Exception as exc:
            self._fail(context, exc)


    async def _execute_node(self, node_name: str, context: GraphContext) -> None:
        """Inject context state into one node and emit its next-node event."""
        try:
            writer = context.get("stream_writer", noop_stream_writer())
            with stream_writer_context(writer):
                execution = self._nodes[node_name].execute(
                    self._copy_state(context["state"])
                )
                timeout = self._node_timeouts[node_name]
                if timeout is None:
                    result = await execution
                else:
                    timeout_scope = asyncio.timeout(timeout)
                    try:
                        async with timeout_scope:
                            result = await execution
                    except TimeoutError as exc:
                        if not timeout_scope.expired():
                            raise
                        raise TimeoutError(
                            f"Graph node `{node_name}` timed out after "
                            f"{timeout:g} seconds."
                        ) from exc
            commands = result if isinstance(result, list) else [result]
            if not commands:
                commands = [Command()]

            state = context["state"]
            next_node = self._default_gotos.get(node_name, END)
            command_context = {**context}

            for command in commands:
                command_context["state"] = state
                # Every command resolves a route independently. Later
                # commands overwrite the route selected by earlier commands;
                # an omitted goto resolves to this node's default route.
                state, next_node = self.apply_command(
                    command,
                    node_name,
                    command_context,
                )

            context["state"] = state
            context["steps"] += 1
            await self._post_next(next_node, context)
        except Exception as exc:
            self._fail(context, exc)


    def apply_command(self, command: Command, node_name: str, context: GraphContext) -> tuple[dict, str]:
        """Return updated state and the target selected by a node command."""
        if not isinstance(command, Command):
            raise TypeError(
                "Node.execute must return a Command or list[Command]."
            )

        update = command.update
        if not isinstance(update, dict):
            raise TypeError("Command.update must be a dict.")
        steps = context.get("steps", 0) + 1
        if steps > self._max_steps:
            raise RecursionError(f"Graph exceeded its maximum of {self._max_steps} steps.")

        state = self._copy_state(context["state"])
        # Command updates are state transfers too. Preserve a KeepRef value
        # when a node returns the marked field explicitly (including when it
        # returns its complete state snapshot).
        update = self._copy_state(update)

        for key, value in update.items():
            if isinstance(value, Reset):
                state[key] = value.value
            elif (
                key in self._auto_increase_keys
                and key in state
            ):
                current_value = state[key]
                add_method = getattr(
                    current_value,
                    "__add__",
                    None,
                )

                if not callable(add_method):
                    raise TypeError(
                        f"State field `{key}` is marked AutoMerge, "
                        f"but {type(current_value).__name__} does not "
                        "provide a callable __add__ method."
                    )

                increased_value = add_method(value)

                if increased_value is NotImplemented:
                    raise TypeError(
                        f"State field `{key}` could not add an update "
                        f"of type {type(value).__name__}."
                    )

                state[key] = increased_value
            else:
                state[key] = value

        next_node = (
            command.goto
            if command.has_goto
            else self._default_gotos.get(node_name, END)
        )
        if next_node is None:
            next_node = END
        if not isinstance(next_node, str):
            raise TypeError("Command.goto must be a string or None.")
        return state, next_node


    async def _post_next(self, node_name: str, context: GraphContext) -> None:
        """Post a node-name event while retaining the invocation context."""
        if node_name not in (START, END) and node_name not in self._nodes:
            raise ValueError(f"Unknown graph node `{node_name}`.")
        await event_pipe_writer.post_event(
            event_type=EventType.WORKFLOW,
            event_name=node_name,
            context=context,
        )


    def _finish(self, context: GraphContext) -> None:
        """Resolve an invocation with the state carried by its END event."""
        completion = context["completion"]
        if not completion.done():
            completion.set_result(self._copy_state(context["state"]))
        _context_store_manager.remove_store_by_run_id(context["run_id"])


    def _fail(self, context: GraphContext, error: Exception) -> None:
        """Resolve an invocation with the exception raised by a graph node."""
        completion = context["completion"]
        if not completion.done():
            completion.set_exception(error)
        _context_store_manager.remove_store_by_run_id(context["run_id"])
