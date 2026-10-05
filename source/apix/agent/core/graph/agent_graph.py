from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager
from typing import Any, get_type_hints

from apix.agent.core.tool.base import ToolFunction
from apix.agent.core.tool import Tool, ToolNode
from apixis.core.graph import BaseNode, GraphManager, NodeGraph
from apixis.core.graph.context import GraphContext


class AgentGraph(NodeGraph):
    """Apix graph that releases invocation-scoped agent resources."""

    @staticmethod
    async def _close_agent_scope(graph_context: GraphContext) -> None:
        """Release resources owned by the completed graph invocation."""
        if graph_context.run_id is None:
            return

        # Import lazily to keep the graph layer independent from optional MCP
        # client dependencies until an AgentGraph is actually invoked.
        from apix.agent.core.tool.mcp import mcp_mgr

        await mcp_mgr.close_agent_scope(graph_context.run_id)

    @asynccontextmanager
    async def _agent_scope(
        self, state: dict | None, graph_context: GraphContext | None
    ) -> AsyncIterator[GraphContext]:
        """Close only the invocation accepted by this call."""
        if graph_context is None:
            if not isinstance(state, dict):
                raise TypeError("Graph state must be a dict.")
            graph_context = self.create_context(state)
        elif state is not None:
            raise TypeError("Pass either state or graph_context, not both.")
        elif not isinstance(graph_context, GraphContext):
            raise TypeError("graph_context must be a GraphContext or None.")

        previous_run_id = graph_context.run_id
        try:
            yield graph_context
        finally:
            # Rejected reuse must not close another active invocation's scope.
            if graph_context.run_id != previous_run_id:
                await self._close_agent_scope(graph_context)

    async def invoke(
        self,
        state: dict | None = None,
        graph_context: GraphContext | None = None,
    ) -> dict:
        """Invoke initial state or a prepared context, then close its scope."""
        async with self._agent_scope(state, graph_context) as context:
            return await super().invoke(graph_context=context)

    async def stream(
        self,
        state: dict | None = None,
        graph_context: GraphContext | None = None,
    ) -> AsyncIterator[Any]:
        """Stream a run and close its scope on completion or cancellation."""
        async with self._agent_scope(state, graph_context) as context:
            # Close the underlying iterator before releasing agent resources.
            async with aclosing(super().stream(graph_context=context)) as stream:
                async for chunk in stream:
                    yield chunk


class AgentGraphCreator(GraphManager):
    """Apix agent graph creator.

    Examples:
        ```python
        class MessageState(TypedDict):
            messages: Annotated[list[str], AutoMerge()]
            status: str

        agent_graph_manager = (
            AgentGraphCreator(MessageState)
            .add_node(first)
        )

        agent_graph = agent_graph_manager.compile_agent("first")
        ```
    """

    def __init__(self, state_schema: type, messages_key: str = "messages"):
        """Create an empty graph definition.

        Args:
            state_schema:
                Annotated state schema containing messages_key. :class:`AgentGraph`
                uses it to discover :class:`AutoMerge` and :class:`KeepRef` fields.
            messages_key: The key in the state dictionary that contains the message list.
        """
        if messages_key not in get_type_hints(state_schema):
            raise KeyError(
                f"The messages_key `{messages_key}` not found in state_schema."
            )
        super().__init__(state_schema)
        self.messages_key = messages_key

    def compile_graph(
        self,
        entry_point: str | list[str] | None,
        *,
        using_namespace: str | None = None,
        exist_ok: bool = False,
    ) -> AgentGraph:
        """Compile a Command-driven agent graph starting at entry_point."""
        return AgentGraph(
            self._nodes,
            entry_point,
            state_schema=self._state_schema,
            using_namespace=using_namespace,
            exist_ok=exist_ok,
        )

    def compile_agent(
        self,
        entry_point: str | list[str] | None,
        *,
        using_namespace: str | None = None,
        exist_ok: bool = False,
    ) -> AgentGraph:
        """Compile this definition using the agent-specific graph runtime."""
        return self.compile_graph(
            entry_point, using_namespace=using_namespace, exist_ok=exist_ok
        )

    def add_tools(
        self,
        tools: list[ToolFunction | Tool],
        node_name: str = "tools",
        *,
        bind_llm_node: str | BaseNode | None = None,
    ):
        """Add tools for agent.

        Tools added by this method will be organized as :class:`ToolNode`.

        Args:
            tools: A list of :data:`ToolFunction` or :class:`Tool`.
            node_name: Optional tools node name.
            bind_llm_node: Optional LLM node name or node object to run next.

        Returns:
            This creator, allowing fluent graph construction.
        """
        self.add_node(
            ToolNode(
                tools,
                node_name,
                messages_key=self.messages_key,
                bind_llm_node=bind_llm_node,
            )
        )
        return self
