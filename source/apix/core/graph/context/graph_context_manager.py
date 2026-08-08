from apix.core.graph.context.graph_context import GraphContext


class _GraphContextManager:
    """Manager for the graph context store."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._store: dict[str, GraphContext] = {}
        self._run_id_index: dict[str, str] = {}
        self._initialized = True

    def add_store(self, store: GraphContext) -> None:
        """Register one fully initialized store in both lookup tables.

        A store ID and run ID may each identify only one active store. Strict
        uniqueness keeps insertion deterministic and lets both registration
        and run-ID removal remain O(1).
        """
        if store.run_id is None or store.graph_context is None:
            raise ValueError(
                "GraphContext must be initialized with set_store() "
                "before registration."
            )
        if store.store_id in self._store:
            raise ValueError(
                f"Graph context store ID `{store.store_id}` is already registered."
            )
        if store.run_id in self._run_id_index:
            raise ValueError(
                f"Graph run ID `{store.run_id}` is already registered."
            )

        self._store[store.store_id] = store
        self._run_id_index[store.run_id] = store.store_id

    def get_store(self, store_id: str) -> GraphContext | None:
        """Get the graph context store for the given store_id."""
        return self._store.get(store_id)

    def remove_store(self, store_id: str) -> None:
        """Remove the graph context store."""
        store = self._store.pop(store_id, None)
        if store is not None and store.run_id is not None:
            self._run_id_index.pop(store.run_id, None)

    def remove_store_by_run_id(self, run_id: str) -> None:
        """Remove the graph context store by run_id."""
        store_id = self._run_id_index.pop(run_id, None)
        if store_id is not None:
            self._store.pop(store_id, None)

    def clear_stores(self) -> None:
        """Clear all graph context stores."""
        self._store.clear()
        self._run_id_index.clear()


_graph_context_manager = _GraphContextManager()
