"""Focused tests for graph invocation context storage."""

from apix.core.graph.context_store import GraphContextStore
from apix.core.graph.context_store.context_store_manager import (
    _GraphContextStoreManager,
)


def _context(run_id: str) -> dict:
    """Build the minimal context needed by the storage layer."""
    return {
        "run_id": run_id,
        "state": {"value": run_id},
    }


def setup_function() -> None:
    """Keep the singleton manager isolated between tests."""
    _GraphContextStoreManager().clear_stores()


def teardown_function() -> None:
    """Do not leak stores into graph runtime tests."""
    _GraphContextStoreManager().clear_stores()


def test_store_generates_unique_id_and_accepts_explicit_id():
    """Stores have a usable ID while allowing callers to choose one."""
    first = GraphContextStore()
    second = GraphContextStore()
    explicit = GraphContextStore("request-42")

    assert first.get_store_id()
    assert first.get_store_id() != second.get_store_id()
    assert explicit.get_store_id() == "request-42"


def test_set_store_preserves_run_and_context_identity():
    """The live graph context remains available to an abort caller."""
    store = GraphContextStore("store")
    context = _context("run-1")

    store.set_store("run-1", context)

    assert store.run_id == "run-1"
    assert store.graph_context is context


def test_manager_is_a_singleton():
    """All graph instances resolve stores through the same manager."""
    assert _GraphContextStoreManager() is _GraphContextStoreManager()


def test_manager_add_get_and_remove_store():
    """A store can be registered, resolved, and removed by its store ID."""
    manager = _GraphContextStoreManager()
    store = GraphContextStore("store")
    store.set_store("run-1", _context("run-1"))

    manager.add_store(store)

    assert manager.get_store("store") is store

    manager.remove_store("store")

    assert manager.get_store("store") is None


def test_manager_remove_store_by_run_id_scans_registered_stores():
    """Graph completion can remove the matching store without an index."""
    manager = _GraphContextStoreManager()
    first = GraphContextStore("first")
    first.set_store("run-1", _context("run-1"))
    second = GraphContextStore("second")
    second.set_store("run-2", _context("run-2"))
    manager.add_store(first)
    manager.add_store(second)

    manager.remove_store_by_run_id("run-2")

    assert manager.get_store("first") is first
    assert manager.get_store("second") is None


def test_replacing_store_id_keeps_latest_store():
    """Reusing a store ID replaces the previous store object."""
    manager = _GraphContextStoreManager()
    old_store = GraphContextStore("store")
    old_store.set_store("old-run", _context("old-run"))
    new_store = GraphContextStore("store")
    new_store.set_store("new-run", _context("new-run"))

    manager.add_store(old_store)
    manager.add_store(new_store)

    assert manager.get_store("store") is new_store


def test_readding_same_store_after_run_change_keeps_current_binding():
    """A mutable store can be rebound and registered again directly."""
    manager = _GraphContextStoreManager()
    store = GraphContextStore("store")
    store.set_store("old-run", _context("old-run"))
    manager.add_store(store)

    store.set_store("new-run", _context("new-run"))
    manager.add_store(store)

    assert manager.get_store("store") is store
    assert manager.get_store("store").run_id == "new-run"


def test_manager_ignores_unknown_removals_and_clears_all_state():
    """Cleanup operations are idempotent and clear all registered stores."""
    manager = _GraphContextStoreManager()
    bound = GraphContextStore("bound")
    bound.set_store("run-1", _context("run-1"))
    unbound = GraphContextStore("unbound")
    manager.add_store(bound)
    manager.add_store(unbound)

    manager.remove_store("missing")
    manager.remove_store_by_run_id("missing")

    assert manager.get_store("bound") is bound
    assert manager.get_store("unbound") is unbound

    manager.clear_stores()

    assert manager._store == {}
