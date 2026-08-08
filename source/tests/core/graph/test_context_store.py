"""Focused tests for graph invocation context storage."""

import pytest

from apix.core.graph.context import GraphContext
from apix.core.graph.context.graph_context_manager import (
    _GraphContextManager,
)


def _context(run_id: str) -> dict:
    """Build the minimal context needed by the storage layer."""
    return {
        "run_id": run_id,
        "state": {"value": run_id},
    }


def setup_function() -> None:
    """Keep the singleton manager isolated between tests."""
    _GraphContextManager().clear_stores()


def teardown_function() -> None:
    """Do not leak stores into graph runtime tests."""
    _GraphContextManager().clear_stores()


def test_store_generates_unique_id_and_accepts_explicit_id():
    """Stores have a usable ID while allowing callers to choose one."""
    first = GraphContext()
    second = GraphContext()
    explicit = GraphContext("request-42")

    assert first.get_store_id()
    assert first.get_store_id() != second.get_store_id()
    assert explicit.get_store_id() == "request-42"


def test_set_store_preserves_run_and_context_identity():
    """The live graph context remains available to an abort caller."""
    store = GraphContext("store")
    context = _context("run-1")

    store.set_store("run-1", context)

    assert store.run_id == "run-1"
    assert store.graph_context is context


def test_manager_is_a_singleton():
    """All graph instances resolve stores through the same manager."""
    assert _GraphContextManager() is _GraphContextManager()


def test_manager_rejects_store_without_run_and_context():
    """Only stores initialized through set_store may be registered."""
    manager = _GraphContextManager()
    store = GraphContext("store")

    with pytest.raises(ValueError, match=r"initialized with set_store\(\)"):
        manager.add_store(store)

    assert manager._store == {}
    assert manager._run_id_index == {}


def test_manager_rejects_partially_initialized_store():
    """Both run_id and graph_context are mandatory manager invariants."""
    manager = _GraphContextManager()
    missing_context = GraphContext("missing-context")
    missing_context.run_id = "run-1"
    missing_run = GraphContext("missing-run")
    missing_run.graph_context = _context("run-2")

    for store in (missing_context, missing_run):
        with pytest.raises(ValueError, match="before registration"):
            manager.add_store(store)

    assert manager._store == {}
    assert manager._run_id_index == {}


def test_manager_add_get_and_remove_store_updates_run_index():
    """Store-ID removal clears the primary table and run-ID index."""
    manager = _GraphContextManager()
    store = GraphContext("store")
    store.set_store("run-1", _context("run-1"))

    manager.add_store(store)

    assert manager.get_store("store") is store
    assert manager._run_id_index == {"run-1": "store"}

    manager.remove_store("store")

    assert manager.get_store("store") is None
    assert manager._run_id_index == {}


def test_manager_remove_store_by_run_id_uses_index():
    """Run-ID removal resolves and deletes its store through the index."""
    manager = _GraphContextManager()
    first = GraphContext("first")
    first.set_store("run-1", _context("run-1"))
    second = GraphContext("second")
    second.set_store("run-2", _context("run-2"))
    manager.add_store(first)
    manager.add_store(second)

    manager.remove_store_by_run_id("run-2")

    assert manager.get_store("first") is first
    assert manager.get_store("second") is None
    assert manager._run_id_index == {"run-1": "first"}


def test_manager_rejects_duplicate_store_id():
    """An active store ID cannot overwrite its existing run mapping."""
    manager = _GraphContextManager()
    old_store = GraphContext("store")
    old_store.set_store("old-run", _context("old-run"))
    new_store = GraphContext("store")
    new_store.set_store("new-run", _context("new-run"))

    manager.add_store(old_store)
    with pytest.raises(ValueError, match="store ID `store` is already registered"):
        manager.add_store(new_store)

    assert manager.get_store("store") is old_store
    assert manager._run_id_index == {"old-run": "store"}


def test_manager_rejects_duplicate_run_id():
    """An active run ID cannot point to more than one store."""
    manager = _GraphContextManager()
    first = GraphContext("first")
    first.set_store("run", _context("run"))
    second = GraphContext("second")
    second.set_store("run", _context("run"))

    manager.add_store(first)
    with pytest.raises(ValueError, match="run ID `run` is already registered"):
        manager.add_store(second)

    assert manager.get_store("first") is first
    assert manager.get_store("second") is None
    assert manager._run_id_index == {"run": "first"}


def test_store_can_be_reused_after_removal():
    """A completed store may be rebound once its old indexes are gone."""
    manager = _GraphContextManager()
    store = GraphContext("store")
    store.set_store("old-run", _context("old-run"))
    manager.add_store(store)
    manager.remove_store_by_run_id("old-run")

    store.set_store("new-run", _context("new-run"))
    manager.add_store(store)

    assert manager.get_store("store") is store
    assert manager._run_id_index == {"new-run": "store"}


def test_manager_ignores_unknown_removals_and_clears_all_state():
    """Cleanup operations are idempotent and clear all registered stores."""
    manager = _GraphContextManager()
    bound = GraphContext("bound")
    bound.set_store("run-1", _context("run-1"))
    second = GraphContext("second")
    second.set_store("run-2", _context("run-2"))
    manager.add_store(bound)
    manager.add_store(second)

    manager.remove_store("missing")
    manager.remove_store_by_run_id("missing")

    assert manager.get_store("bound") is bound
    assert manager.get_store("second") is second
    assert manager._run_id_index == {
        "run-1": "bound",
        "run-2": "second",
    }

    manager.clear_stores()

    assert manager._store == {}
    assert manager._run_id_index == {}
