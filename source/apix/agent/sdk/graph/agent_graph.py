from apix.core.graph import NodeGraph, GraphManager


class AgentGraphCreator(GraphManager):
    """Apix agent graph creator."""

    def __init__(self):
        super().__init__()

    def add_tool_router(
        self, 
        bot_node_name: str = 'bot', 
        tool_node_name: str = 'tools', 
        messages_key: str = 'messages'
    ):
        pass


class AgentGraph(NodeGraph):
    """Apix agent graph."""

    def __init__(self):
        super().__init__()


    async def invoke(self, state):
        return await super().invoke(state)
    
    async def stream(self, state):
        return super().stream(state)