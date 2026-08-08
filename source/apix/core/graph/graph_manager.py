"""Graph construction utilities."""

import inspect
from collections.abc import Mapping

from apix.core.graph.base import END, START, Command, NodeFunction
from apix.core.graph.node import BaseNode, Node
from apix.core.graph.node_graph import NodeGraph


class GraphManager:
    """Build the node and transition definition for a stateless graph.

    Graph state is never retained by this builder or the compiled graph. It is
    carried from node to node in the event context instead. Every graph must
    define a transition from :data:`START`; nodes without a transition finish
    by routing to :data:`END`.

    Examples:
        ```python
        class AccumulatingState(TypedDict):
            messages: Annotated[list[str], AutoMerge()]
            status: str

        manager = GraphManager(AccumulatingState)
        ```
    """

    def __init__(
        self,
        state_schema: type | None = None,
    ):
        """Create an empty graph definition.

        Args:
            state_schema:
                Optional annotated state schema used as the default for each
                invocation's :class:`GraphContext`. Omitting it preserves
                normal dictionary overwrite behaviour.
        """
        self._state_schema = state_schema
        self._nodes: dict[str, BaseNode] = {}
        self._node_timeouts: dict[str, float | None] = {}
        self._default_gotos: dict[str, str] = {}
        self._generated_names: set[str] = set()


    def has_node(self, node_name: str) -> bool:
        """Returns whether this graph manager has a node named `node_name`.
        """
        return node_name in self._nodes


    def add_node(
        self,
        node_func: NodeFunction | BaseNode,
        node_name: str | None = None,
        *,
        timeout: float | None = None,
    ):
        """Register a user-defined state-processing node.

        Args:
            node_func: Synchronous or asynchronous node callable.
            node_name: Unique node name, defaulting to the callable's name.
            timeout: Maximum node execution time in seconds. ``None`` and
                values less than or equal to zero wait indefinitely.

        Returns:
            This manager, allowing fluent graph construction.

        Raises:
            ValueError: If the name is reserved, already registered, or the
                timeout is not finite.
            TypeError: If timeout is not a number or ``None``.
        """
        if not isinstance(node_func, BaseNode):
            node = Node(node_func, node_name)
        else:
            node = node_func

        if node.name in (START, END):
            raise ValueError(f"`{node.name}` is a reserved graph node name.")
        if node.name in self._nodes:
            raise ValueError(f"Node `{node.name}` is already registered.")

        normalised_timeout = NodeGraph.normalise_timeout(timeout)
        self._nodes[node.name] = node
        self._node_timeouts[node.name] = normalised_timeout
        return self


    def add_nodes(self, node_list: list[NodeFunction | BaseNode]):
        """Register several nodes using each callable's name.

        Args:
            node_list: Synchronous or asynchronous node callables.

        Returns:
            This manager, allowing fluent graph construction.
        """
        for node_func in node_list:
            self.add_node(node_func)
        return self


    def _require_endpoint(self, node_name: str, *, source: bool = False) -> None:
        """Validate a transition endpoint, including the predefined nodes."""
        if source and node_name == END:
            raise ValueError("`END` cannot have an outgoing transition.")
        if node_name not in (START, END) and node_name not in self._nodes:
            raise ValueError(f"Node `{node_name}` has not been added.")


    def _set_transition(self, source: str, target: str) -> None:
        """Associate one manager-defined outgoing transition with ``source``."""
        if source in self._default_gotos:
            raise ValueError(f"Node `{source}` already has an outgoing transition.")
        self._default_gotos[source] = target


    def _generated_node_name(self, kind: str, left: str, function: NodeFunction) -> str:
        """Create a unique private node name for a condition or router."""
        base = f"__{kind}__{left}__{function.__name__}"
        name = base
        suffix = 2
        while name in self._nodes or name in self._generated_names:
            name = f"{base}_{suffix}"
            suffix += 1
        self._generated_names.add(name)
        return name


    @staticmethod
    async def _call(func: NodeFunction, state: dict):
        """Call ``func`` and await its result only when it is awaitable."""
        result = func(state)
        return await result if inspect.isawaitable(result) else result


    def add_edge(
        self,
        l_node: str,
        r_node: str,
        condition: NodeFunction | None = None,
    ):
        """Add a direct or conditional transition between graph nodes.

        When ``condition`` is supplied it becomes an internal node: ``True``
        routes to ``r_node`` and ``False`` routes to :data:`END`. Omitting it
        creates a direct transition, which is normally used for
        ``START -> first_node`` and ``last_node -> END``.
        """
        self._require_endpoint(l_node, source=True)
        self._require_endpoint(r_node)
        if condition is None:
            self._set_transition(l_node, r_node)
            return self
        if not callable(condition):
            raise TypeError("`condition` must be callable.")

        condition_name = self._generated_node_name("condition", l_node, condition)

        async def condition_node(state: dict) -> Command:
            """Evaluate the edge condition and route to its target when true."""
            result = await self._call(condition, state)
            if not isinstance(result, bool):
                raise TypeError("A condition function must return bool.")
            return Command(update={}, goto=r_node if result else END)

        self._nodes[condition_name] = Node(condition_node, condition_name)
        self._set_transition(l_node, condition_name)
        return self


    def add_router(self, l_node: str, r_nodes: list[str], router: NodeFunction):
        """Add an internal router node after ``l_node``.

        The router receives the state from the event context and must select a
        name from ``r_nodes``. A mapping containing ``goto`` is also accepted.
        :data:`END` may be used as one of the route targets.
        """
        self._require_endpoint(l_node, source=True)
        if not r_nodes:
            raise ValueError("`r_nodes` must contain at least one target node.")
        for node_name in r_nodes:
            self._require_endpoint(node_name)
        if not callable(router):
            raise TypeError("`router` must be callable.")

        router_name = self._generated_node_name("router", l_node, router)
        targets = set(r_nodes)

        async def router_node(state: dict) -> Command:
            """Run the router and turn its selected target into a command."""
            result = await self._call(router, state)
            if isinstance(result, Command):
                result = result.goto if result.has_goto else None
            elif isinstance(result, Mapping) and "goto" in result:
                result = result["goto"]
            if result not in targets:
                raise ValueError(f"Router for `{l_node}` returned invalid target `{result}`.")
            return Command(update={}, goto=result)

        self._nodes[router_name] = Node(router_node, router_name)
        self._set_transition(l_node, router_name)
        return self


    def compile_graph(
        self,
        using_namespace: str | None = None,
    ) -> NodeGraph:
        """Compile this definition into an event-listening :class:`NodeGraph`.

        Args:
            using_namespace: Namespace used by the compiled graph's event
                listeners. ``None`` and an empty string select the global
                namespace.

        Raises:
            ValueError: If no transition has been defined from :data:`START`.
        """
        if START not in self._default_gotos:
            raise ValueError("A graph must define an outgoing transition from `START`.")
        return NodeGraph(
            self._nodes,
            self._default_gotos,
            node_timeouts=self._node_timeouts,
            state_schema=self._state_schema,
            using_namespace=using_namespace,
        )
