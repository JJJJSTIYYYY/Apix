from uuid import uuid4

from apix.core.graph.context.base import GraphContext


class GraphContextStore:
    """Graph context store for managing the context of graph runs."""

    store_id: str | None
    run_id: str | None
    graph_context: GraphContext | None

    def __init__(self, store_id: str | None = None):
        self.store_id = store_id or uuid4().hex
        self.run_id = None
        self.graph_context = None

    def get_store_id(self) -> str:
        """Get the unique identifier of the graph context store."""
        return self.store_id

    def set_store(self, run_id: str, graph_context: GraphContext):
        """Set the graph context store with the given run_id and graph_context."""
        self.run_id = run_id
        self.graph_context = graph_context

    