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
        self._run_id_index: dict[str, str] = {}  # run_id to store_id mapping
        self._initialized = True

    def add_store(self, store: GraphContextStore) -> None:
        """Add a graph context store."""
        # Remove old run_id index if replacing an existing store.
        old_store = self._store.get(store.store_id)
        if old_store and old_store.run_id:
            self._run_id_index.pop(old_store.run_id, None)

        self._store[store.store_id] = store

        if store.run_id:
            self._run_id_index[store.run_id] = store.store_id

    def get_store(self, store_id: str) -> GraphContextStore | None:
        """Get the graph context store for the given store_id."""
        return self._store.get(store_id)

    def remove_store(self, store_id: str) -> None:
        """Remove the graph context store."""
        store = self._store.pop(store_id, None)
        if store and store.run_id:
            self._run_id_index.pop(store.run_id, None)

    def remove_store_by_run_id(self, run_id: str) -> None:
        """Remove the graph context store by run_id."""
        store_id = self._run_id_index.pop(run_id, None)
        if store_id:
            self._store.pop(store_id, None)

    def clear_stores(self) -> None:
        """Clear all graph context stores."""
        self._store.clear()
        self._run_id_index.clear()


_context_store_manager = _GraphContextStoreManager()