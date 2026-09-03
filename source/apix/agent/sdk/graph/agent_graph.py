from collections.abc import AsyncIterator
from typing import Any, get_type_hints

from apix.agent.sdk.tool.base import ToolFunction
from apix.agent.sdk.tool.tool_node import Tool, ToolNode
from apix.core.graph import GraphManager, NodeGraph
from apix.core.graph.base import START, _acquire_namespace
from apix.core.graph.context import GraphContext


class AgentGraph(NodeGraph):
    """Apix graph that releases invocation-scoped agent resources."""

    @staticmethod
    async def _close_agent_scope(graph_context: GraphContext) -> None:
        """Release resources owned by the completed graph invocation."""
        if graph_context.run_id is None:
            return

        # Import lazily to keep the graph layer independent from optional MCP
        # client dependencies until an AgentGraph is actually invoked.
        from apix.agent.sdk.tool.mcp import mcp_mgr

        await mcp_mgr.close_agent_scope(graph_context.run_id)

    async def invoke(
        self,
        state: dict,
        graph_context: GraphContext | None = None,
    ) -> dict:
        """Invoke the graph and close its agent-scoped resources afterward."""
        context = graph_context or self._context_factory()
        try:
            return await super().invoke(state, context)
        finally:
            await self._close_agent_scope(context)

    async def stream(
        self,
        state: dict,
        graph_context: GraphContext | None = None,
    ) -> AsyncIterator[Any]:
        """Stream the graph and close its scope on completion or cancellation."""
        context = graph_context or self._context_factory()
        try:
            async for chunk in super().stream(state, context):
                yield chunk
        finally:
            await self._close_agent_scope(context)


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
            .add_edge(START, "first")
        )

        agent_graph = agent_graph_manager.compile_agent()
        ```
    """

    def __init__(
        self, 
        state_schema: type,
        messages_key: str = 'messages'
    ):
        """Create an empty graph definition.

        Args:
            state_schema:
                Optional annotated state schema. :class:`AgentGraph` uses it to
                discover fields marked with :class:`AutoMerge` and :class:`KeepRef`. 
                Omitting it preserves normal dictionary overwrite behaviour.
            messages_key: The key in the state dictionary that contains the message list.
        """
        if messages_key not in get_type_hints(state_schema):
            raise KeyError(f"The messages_key `{messages_key}` not found in state_schema.")
        super().__init__(state_schema)
        self.messages_key = messages_key

    def compile_graph(
        self,
        using_namespace: str | None = None,
        exist_ok: bool = False,
    ) -> AgentGraph:
        """Compile this definition into an :class:`AgentGraph`."""
        if START not in self._default_gotos:
            raise ValueError(
                "A graph must define an outgoing transition from `START`."
            )

        namespace = using_namespace or ""
        return _acquire_namespace(
            namespace,
            lambda: AgentGraph(
                self._nodes,
                self._default_gotos,
                state_schema=self._state_schema,
                using_namespace=namespace,
            ),
            replace_existed=exist_ok,
        )

    def compile_agent(
        self,
        using_namespace: str | None = None,
        exist_ok: bool = False,
    ) -> AgentGraph:
        """Compile this definition using the agent-specific graph runtime."""
        return self.compile_graph(using_namespace, exist_ok)

    def add_tools(
        self,
        tools: list[ToolFunction | Tool],
        node_name: str = 'tools'
    ):  
        """Add tools for agent. 
        
        Tools added by this method will be organized as :class:`ToolNode`.

        Args:
            tools: A list of :data:`ToolFunction` or :class:`Tool`.
            node_name: Optional tools node name.

        Returns:
            This creator, allowing fluent graph construction.
        """
        parsed_tools = []
        for tool in tools:
            if not isinstance(tool, Tool):
                tool = Tool(tool)
            parsed_tools.append(tool)

        tool_node = ToolNode(parsed_tools, node_name)
        self.add_node(tool_node)
        return self
