from apix.core.graph import NodeGraph


class AgentGraph(NodeGraph):
    """Apix agent graph."""

    def __init__(self):
        super().__init__()


    async def invoke(self, state):
        return await super().invoke(state)
    
    async def stream(self, state):
        return super().stream(state)