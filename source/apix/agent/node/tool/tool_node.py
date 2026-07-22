from apix.core.graph.base import NodeFunction
from apix.core.graph.node import BaseNode


class ToolNode(BaseNode):
    """Tool node for agent.
    """

    name: str
    func: list[NodeFunction]
    
    def __init__(self, func: NodeFunction | list[NodeFunction], name: str):
        """Create a node.

        Args:
            func: A NodeFunction instance or a list of NodeFunction instances.
            name: The name of the tool node. Must be a non-empty string.

        Raises:
            ValueError: If `func` is not a NodeFunction or a list of NodeFunctions, 
                or if `name` is empty.
        """
        if not isinstance(func, list):
            if not isinstance(func, NodeFunction):
                raise ValueError("A tool node requires a function list.")
            else:
                func = [func]

        if not name:
            raise ValueError("A tool node requires a name.")
        
        self.name = name
        self.func = []
        
        for f in func:
            self.func.append(self._wrap_func(func))


    def execute(self, state):
        pass