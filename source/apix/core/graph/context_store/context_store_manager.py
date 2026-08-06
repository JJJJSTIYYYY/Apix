from apix.core.graph.context_store.graph_context_store import GraphContextStore


class _GraphContextStoreManager:
    """Manager for the graph context store."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._store: dict[str, GraphContextStore] = {}
        self._initialized = True

    def add_store(self, store: GraphContextStore) -> None:
        """Add a graph context store."""
        self._store[store.store_id] = store

    def get_store(self, store_id: str) -> GraphContextStore | None:
        """Get the graph context store for the given store_id."""
        return self._store.get(store_id)

    def remove_store(self, store_id: str) -> None:
        """Remove the graph context store."""
        self._store.pop(store_id, None)

    def remove_store_by_run_id(self, run_id: str) -> None:
        """Remove the graph context store by run_id."""
        store_id = next(
            (
                store_id
                for store_id, store in self._store.items()
                if store.run_id == run_id
            ),
            None,
        )
        if store_id is not None:
            self._store.pop(store_id, None)

    def clear_stores(self) -> None:
        """Clear all graph context stores."""
        self._store.clear()


_context_store_manager = _GraphContextStoreManager()