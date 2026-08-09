from apix.agent.sdk.utils.message import AnyMessage, ApixAiMessage
from apix.core.graph import NodeGraph, GraphManager
from apix.core.graph.base import END


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
        state_schema: type | None = None,
        messages_key: str = 'messages'
    ):
        """Create an empty graph definition.

        Args:
            state_schema:
                Optional annotated state schema. :class:`AgentGraph` uses it to
                discover fields marked with :class:`AutoMerge`. Omitting it
                preserves normal dictionary overwrite behaviour.
            messages_key: The key in the state dictionary that contains the message list.
        """
        super().__init__(state_schema)
        self.messages_key = messages_key

    def compile_agent(self) -> AgentGraph:
        return super().compile_graph()

    def add_prebuilt_tools_router(
        self, 
        bot_node_name: str = 'bot', 
        tool_node_name: str = 'tools', 
        next_default: str = END,
    ):
        """Add a router node between bot node and tool node.
        Auto bind tools for a bot instance.
        
        Args:
            bot_node_name: The bot node's name.
            tool_node_name: The tool node's name.
            next_default: The default node to enter when a tool node should not be entered.

        Notes:
            If a bot node has other routing destinations besides the tool node and a default node, use :data:`add_router` instead.
        """
        messages_key = self.messages_key
        def should_call_tool(state):
            messages: list[AnyMessage] = state.get(messages_key, []) or []
            if not messages:
                return next_default
            if not isinstance(messages[-1], ApixAiMessage) or not messages[-1].tool_calls:
                return next_default
            return tool_node_name

        self.add_router(bot_node_name, [next_default, tool_node_name], should_call_tool)