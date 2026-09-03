"""Stateless, event-driven graph runtime."""

import asyncio
from uuid import uuid4
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from functools import partial
from typing import Any

from apix.core.event import (
    EVENT_PIPE,
    ApixEvent,
    EventType,
    APIX_EVENT_LOOP,
    delete_handler_from_registry,
    subscribe,
)
from apix.core.graph.base import (
    END,
    GRAPH_DISPATCH,
    START,
    Command,
    Reset,
    _copy_state,
    _release_namespace,
    _get_node_listener_name,
    get_node_name_in_namespace,
)
from apix.core.graph.context import GraphContext
from apix.core.graph.context.manager import apix_graph_context
from apix.core.graph.interrupter.base import Block
from apix.core.graph.interrupter.graph_interrupter import interrupted_hook
from apix.core.graph.node import BaseNode
from apix.core.graph.context import (
    StreamChannel,
    StreamWriter,
    noop_stream_writer,
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
        max_steps: int = 1024,
        state_schema: type | None = None,
        using_namespace: str | None = None,
    ):
        """Create a compiled graph and register listeners for all node names.

        Args:
            nodes: Nodes keyed by their graph names.
            default_gotos: Manager-defined transitions.
            max_steps: Maximum number of node-dispatch batches in one run.
            state_schema: Default annotated schema for invocation contexts.
                Fields marked with ``Annotated[..., AutoMerge()]`` are
                combined through their current value's ``__add__`` method.
            using_namespace: Namespace used by the graph's event listeners.
                ``None`` and an empty string select the global namespace.
        """
        if using_namespace == '<global>':
            raise ValueError("Namespace `<global>` is a preserved namespace.")
        self._nodes = dict(nodes)
        self._default_gotos = dict(default_gotos)
        self._max_steps = max_steps
        # Validate once at compilation, then create invocation-local contexts
        # carrying all schema-derived state behavior.
        GraphContext(state_schema)
        self._context_factory = partial(GraphContext, state_schema)
        self._invocation_count = 0
        self._listener_namespace = using_namespace or ""
        self._listener_handler_names: list[str] = []
        self._dispatch_event_name = get_node_name_in_namespace(
            GRAPH_DISPATCH,
            self._listener_namespace,
        )
        self._decomposed = False
        self._register_node_listeners()


    def __enter__(self):
        return self

    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.decompose()
        return False


    def _register_node_listeners(self) -> None:
        """Subscribe the graph's single namespace-scoped dispatch handler."""
        async def dispatch_node(event: ApixEvent) -> None:
            """Dispatch an active context to its currently targeted node."""
            context = event.context
            if not self._is_active_context(context):
                return

            target_node_name = context.target_node_name
            if target_node_name == START:
                await self._execute_start(context)
            elif target_node_name == END:
                self._finish(context)
            elif target_node_name == []:
                self._finish(context)
            else:
                await self._execute_node(target_node_name, context)

        dispatch_node.__name__ = _get_node_listener_name(
            GRAPH_DISPATCH,
            self._listener_namespace,
        )
        try:
            subscribe(
                self._dispatch_event_name,
                exist_ok=False,
            )(dispatch_node)
            self._listener_handler_names.append(dispatch_node.__name__)
        except BaseException:
            self._unregister_node_listeners()
            raise


    def _unregister_node_listeners(self) -> None:
        """Remove every event handler successfully registered by this graph."""
        for handler_name in self._listener_handler_names:
            delete_handler_from_registry(handler_name)
        self._listener_handler_names.clear()


    def set_max_steps(self, steps: int):
        self._ensure_not_decomposed()
        self._max_steps = steps
        return self


    def _ensure_not_decomposed(self) -> None:
        """Reject business operations on an invalidated graph."""
        if self._decomposed:
            raise RuntimeError("NodeGraph has been decomposed.")


    def decompose(self) -> None:
        """Invalidate this graph and unregister all of its event listeners.

        Decomposition is idempotent. A graph with an invocation in progress
        cannot be decomposed because removing its listeners would leave that
        invocation without a completion path.

        Raises:
            RuntimeError: If an invocation is currently in progress.
        """
        if self._decomposed:
            return
        if self._invocation_count:
            raise RuntimeError(
                "Cannot decompose a NodeGraph while invocations are active."
            )

        self._decomposed = True
        self._unregister_node_listeners()
        _release_namespace(self)


    def _is_active_context(
        self,
        context: object,
    ) -> bool:
        """Return whether an event context belongs to an active invocation.

        Context lifecycle and namespace ownership are the single source of
        truth; the graph does not retain a duplicate run registry.
        """
        if (
            not isinstance(context, GraphContext)
            or not context._belongs_to(self._listener_namespace)
        ):
            return False
        if not context.is_bound:
            return False
        return context.is_active


    async def invoke(
        self,
        state: dict,
        graph_context: GraphContext | None = None,
    ) -> dict:
        """Start a graph invocation at :data:`START` and return its final state.

        The input state is deep-copied into the first event context. Independent
        invocations may run concurrently because all evolving state stays in
        their event contexts rather than on this graph object.

        Args:
            state: Initial graph state.
            graph_context: Optional recoverable invocation context. Retaining
                this object lets the caller abort the run or restore its
                snapshot into a new context.
        """
        self._ensure_not_decomposed()
        self._invocation_count += 1
        try:
            return await self._invoke(
                state,
                noop_stream_writer(),
                graph_context,
            )
        finally:
            self._invocation_count -= 1


    async def stream(
        self,
        state: dict,
        graph_context: GraphContext | None = None,
    ) -> AsyncIterator[Any]:
        """Yield custom chunks emitted by nodes during one graph invocation.

        Nodes emit chunks by calling :func:`get_stream_writer` and invoking the
        returned writer. The iterator ends when the graph reaches :data:`END`.
        If graph execution fails, queued chunks are yielded first and then the
        original exception is propagated to the stream consumer.

        Args:
            state: Initial graph state. It is deep-copied before execution.
            graph_context: Optional recoverable invocation context. Retaining
                this object lets the caller abort the stream or restore its
                snapshot into a new context.

        Yields:
            Custom chunks in the order in which nodes emitted them.
        """
        self._ensure_not_decomposed()
        self._invocation_count += 1
        channel = StreamChannel()
        execution_task = asyncio.create_task(
            self._invoke(state, channel.writer, graph_context),
            name=f"graph-stream-{uuid4().hex}",
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
            self._invocation_count -= 1


    async def abort(self, graph_context: GraphContext) -> None:
        """Interrupt the invocation represented by ``graph_context``.

        The graph's :data:`END` node is not executed, so the invocation's
        completion future is resolved with the most recently saved state
        snapshot. Any queued chunks are yielded before a stream ends.

        When this method is called, the graph execution is not interrupted
        immediately. A snapshot is captured immediately before each ordinary
        node starts. The current node may continue running, but its result
        cannot be committed or routed after the abort. The :meth:`invoke` and
        :meth:`stream` interfaces return immediately with the captured state.

        The same operation is also available directly through
        :meth:`GraphContext.abort`.

        Raises:
            TypeError: If ``graph_context`` is not a GraphContext instance.
            ValueError: If the context is not active in this graph.
        """
        self._ensure_not_decomposed()
        if not isinstance(graph_context, GraphContext):
            raise TypeError("NodeGraph.abort requires a GraphContext instance.")

        if not self._is_active_context(graph_context):
            raise ValueError("Graph context is not active in this graph.")

        graph_context.abort()


    async def _invoke(
        self,
        state: dict,
        stream_writer: StreamWriter,
        graph_context: GraphContext | None = None,
    ) -> dict:
        """Run a graph with the writer assigned to each executing node."""
        if not isinstance(state, dict):
            raise TypeError("Graph state must be a dict.")
        if graph_context is not None and not isinstance(
            graph_context,
            GraphContext,
        ):
            raise TypeError("graph_context must be a GraphContext or None.")
        context = graph_context or self._context_factory()
        if graph_context is not None:
            context._adopt_default_state_schema(self._context_factory())

        run_id = "graph-"+uuid4().hex
        completion = asyncio.get_running_loop().create_future()
        try:
            await APIX_EVENT_LOOP.start()
            first_node = context._bind(
                context_namespace=self._listener_namespace,
                run_id=run_id,
                state=state,
                completion=completion,
                stream_writer=stream_writer,
            )
            await self._post_next(first_node, context)
            return await completion
        except asyncio.CancelledError:
            # Cancelling ``await completion`` also cancels the Future before
            # control reaches this handler, so ``is_active`` is already false.
            # Lifecycle status remains the authoritative signal that a bound
            # invocation still needs to be aborted.
            if context.status == "running":
                context.abort()
            raise
        except Exception as exc:
            if context.status in ("pending", "running"):
                context._fail(exc)
            raise


    async def _execute_start(self, context: GraphContext) -> None:
        """Route the predefined start node to its configured successor."""
        try:
            await self._post_next(self._default_gotos[START], context)
        except Exception as exc:
            if context.is_active:
                self._fail(context, exc)


    async def _execute_one_node(
        self,
        node_name: str,
        context: GraphContext,
    ) -> Command | list[Command]:
        """Execute one batch member with an isolated state copy."""
        node = self._nodes[node_name]
        execution = node.execute(
            _copy_state(context.state, context._keep_ref_keys)
        )
        timeout = node.timeout
        if timeout is None:
            return await execution

        timeout_scope = asyncio.timeout(timeout)
        try:
            async with timeout_scope:
                return await execution
        except TimeoutError as exc:
            if not timeout_scope.expired():
                raise
            raise TimeoutError(
                f"Graph node `{node_name}` timed out after "
                f"{timeout:g} seconds."
            ) from exc

    async def _execute_node(
        self,
        node_name: str | list[str],
        context: GraphContext,
    ) -> None:
        """Execute one node or one concurrently scheduled node batch."""
        node_names = self._normalise_targets(node_name)
        context.take_a_snapshot()
        try:
            with apix_graph_context(context):
                tasks = [
                    asyncio.create_task(
                        self._execute_one_node(current_name, context),
                        name=f"graph-node-{current_name}-{context.run_id}",
                    )
                    for current_name in node_names
                ]
                results = await BaseNode._gather_tasks_in_order(tasks)

            # An aborted attempt may finish its old node after a caller has
            # already received the saved snapshot. Its result must never
            # mutate a recovered context or enqueue another event.
            if not context.is_active:
                return

            next_node = self.apply_command(
                results[0] if isinstance(node_name, str) else results,
                node_name,
                context,
            )

            context.steps += 1
            await self._post_next(next_node, context)
        except Exception as exc:
            if context.is_active:
                self._fail(context, exc)


    def apply_command(
        self,
        command: Command | list[Command] | list[Command | list[Command]],
        node_name: str | list[str],
        context: GraphContext,
    ) -> str | list[str]:
        """Apply a completed batch in order and collect its ordered routes.

        The checkpoint taken before node execution is the rollback boundary.
        Commands therefore update the live context state directly. If applying
        a later command fails, recovery starts from that checkpoint rather than
        rolling the live state back in place.
        """
        node_names = self._normalise_targets(node_name)
        command_groups = self._normalise_command_groups(command, node_names)

        if context.steps >= self._max_steps:
            raise RecursionError(
                f"Graph exceeded its maximum of {self._max_steps} steps."
            )

        updated_normal_keys: set[str] = set()
        routes: list[str] = []
        for current_node, commands in zip(node_names, command_groups):
            current_node_normal_keys: set[str] = set()
            for current_command in commands:
                if not isinstance(current_command.update, dict):
                    raise TypeError("Command.update must be a dict.")
                update = _copy_state(
                    current_command.update,
                    context._keep_ref_keys,
                )
                for key, value in update.items():
                    if key not in context._auto_merge_keys:
                        if (
                            key in updated_normal_keys
                            and key not in current_node_normal_keys
                        ):
                            raise ValueError(
                                f"Concurrent node `{current_node}` updates "
                                f"non-AutoMerge state field `{key}` more than once."
                            )
                        updated_normal_keys.add(key)
                        current_node_normal_keys.add(key)

                    if isinstance(value, Reset):
                        context.state[key] = value.value
                    elif key in context._auto_merge_keys and key in context.state:
                        current_value = context.state[key]
                        add_method = getattr(current_value, "__add__", None)
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
                        context.state[key] = increased_value
                    else:
                        context.state[key] = value

                goto = current_command.goto
                if goto is None:
                    goto = self._default_gotos.get(current_node, END)
                if not BaseNode._is_valid_goto(goto):
                    raise TypeError(
                        "Command.goto must be a string or None, or a list of strings."
                    )
                routes.extend(goto if isinstance(goto, list) else [goto])

        return self._normalise_routes(routes)

    @staticmethod
    def _normalise_command_groups(
        command: Command | list[Command] | list[Command | list[Command]],
        node_names: list[str],
    ) -> list[list[Command]]:
        """Normalise results without losing their source-node boundaries."""
        if len(node_names) == 1:
            if isinstance(command, Command):
                return [[command]]
            if isinstance(command, list) and all(
                isinstance(item, Command) for item in command
            ):
                return [command or [Command()]]
            raise TypeError("Node.execute must return a Command or list[Command].")

        if not isinstance(command, list) or len(command) != len(node_names):
            raise TypeError("A concurrent batch must return one result per node.")
        groups: list[list[Command]] = []
        for result in command:
            if isinstance(result, Command):
                groups.append([result])
            elif isinstance(result, list) and all(
                isinstance(item, Command) for item in result
            ):
                groups.append(result or [Command()])
            else:
                raise TypeError(
                    "Node.execute must return a Command or list[Command]."
                )
        return groups

    @staticmethod
    def _normalise_targets(target: str | list[str]) -> list[str]:
        """Validate a non-empty execution target and return a batch list."""
        if isinstance(target, str):
            return [target]
        if isinstance(target, list) and target and all(
            isinstance(item, str) for item in target
        ):
            return list(target)
        raise TypeError("Graph target must be a string or non-empty list of strings.")

    @staticmethod
    def _normalise_routes(routes: list[str]) -> str | list[str]:
        """Filter END when work remains and perform stable de-duplication."""
        if not routes:
            return []
        unique = list(dict.fromkeys(routes))
        runnable = [route for route in unique if route != END]
        if not runnable:
            return END
        return runnable[0] if len(runnable) == 1 else runnable


    async def _post_next(
        self,
        node_name: str | list[str],
        context: GraphContext,
    ) -> None:
        """Target one node or concurrent batch and post one dispatch."""
        node_names = [node_name] if isinstance(node_name, str) else node_name
        if not isinstance(node_names, list) or not all(
            isinstance(item, str) for item in node_names
        ):
            raise TypeError("Graph target must be a string or list of strings.")
        for current_name in node_names:
            if current_name not in (START, END) and current_name not in self._nodes:
                raise ValueError(f"Unknown graph node `{current_name}`.")
        context._set_target_node(node_name)
        await EVENT_PIPE.post_event(
            event_type=EventType.WORKFLOW,
            event_name=self._dispatch_event_name,
            context=context,
        )


    def _finish(self, context: GraphContext) -> None:
        """Resolve an invocation with the state carried by its END event."""
        context._finish()


    def _fail(self, context: GraphContext, error: Exception) -> None:
        """Resolve an invocation with the exception raised by a graph node."""
        context._fail(error)
        

    def add_interrupted_hook(
        self,
        afunc: Callable[[Block], Awaitable[None]],
    ) -> Callable[[Block], Awaitable[None]]:
        """Register a graph-owned interruption callback.

        The graph's namespace is selected automatically. The callback is
        unregistered by :meth:`decompose`, preventing a replacement graph from
        accidentally dispatching blocks to a stale callback.
        """
        self._ensure_not_decomposed()

        interrupted_hook(
            self._listener_namespace,
            exist_ok=False,
        )(afunc)
        self._listener_handler_names.append(afunc.__name__)
        return afunc
