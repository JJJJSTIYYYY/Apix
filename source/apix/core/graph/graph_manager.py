from typing import Awaitable, Callable

from apix.core.graph.node_graph import NodeGraph


class GraphManager:
    """
    Manage a node graph with state.
    """

    def __init__(self):
        pass

    def add_node(self, node_func: Callable | Awaitable, node_name: str = None):
        """
        Add a graph node.

        Args:
            node_func: a sync or async Callable instance.
            node_name: a unique name for node_func, defaults to the function name.
        """
        pass

    def add_edge(self, l_node: str, r_node: str, condition: Callable | Awaitable):
        """
        Add a graph edge between two nodes in the manager.
        Direction: l_node -> r_node.

        Args:
            l_node: left node's name that has been added to the manager.
            r_node: right node's name that has been added to the manager.
            condition: a sync or async Callable instance; the right node will not be entered if the condition function returns False.
        """
        pass

    def add_router(self, l_node: str, r_nodes: list[str], router: Callable | Awaitable):
        """
        Add a graph router between two nodes in the manager.
        Direction: l_node -> r_nodes.

        Args:
            l_node: left node's name that has been added to the manager.
            r_nodes: a list of right node names that have been added to the manager.
            router: a sync or async Callable instance; the graph will choose the node whose name is returned by the router.
        """
        pass

    def compile_graph(self) -> NodeGraph:
        """
        Compile and return the graph according to the added nodes and edges.
        """
        pass

    def invoke_graph(self, state: dict):
        """
        Invoke the graph with an initial state.
        """
        pass