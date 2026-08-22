from typing import get_type_hints

from apix.agent.sdk.tool.base import ToolFunction
from apix.agent.sdk.tool.tool_node import Tool, ToolNode
from apix.core.graph import NodeGraph, GraphManager


class AgentGraph(NodeGraph):
    """Apix agent graph. Thick wrapper for :class:`NodeGraph`."""


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

    def compile_agent(self) -> AgentGraph:
        return super().compile_graph()

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