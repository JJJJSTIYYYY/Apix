"""Focused tests for invocation-local graph context binding."""

import asyncio

import pytest

from apix.core.graph.context import (
    GraphContext,
    StreamWriter,
    apix_graph_context,
    get_graph_context,
    get_stream_writer,
)


def _context_with_writer() -> tuple[GraphContext, StreamWriter]:
    """Create a context carrying a node-facing stream writer."""
    context = GraphContext()
    writer = StreamWriter(lambda chunk: None)
    context.stream_writer = writer
    return context, writer


def test_graph_accessors_require_bound_context():
    """Context-dependent helpers reject calls outside node execution."""
    with pytest.raises(
        RuntimeError,
        match="get_graph_context.*only available while a graph context is bound",
    ):
        get_graph_context()

    with pytest.raises(
        RuntimeError,
        match="get_stream_writer.*only available while a graph context is bound",
    ):
        get_stream_writer()


def test_apix_graph_context_exposes_context_and_its_writer():
    """One binding supplies both graph state and the current stream writer."""
    context, writer = _context_with_writer()

    with apix_graph_context(context):
        assert get_graph_context() is context
        assert get_stream_writer() is writer


def test_bound_context_without_writer_rejects_stream_access():
    """A graph context alone does not imply an active node stream writer."""
    context = GraphContext()

    with apix_graph_context(context):
        assert get_graph_context() is context
        with pytest.raises(
            RuntimeError,
            match="get_stream_writer.*only available while a graph node is running",
        ):
            get_stream_writer()


def test_nested_apix_graph_context_restores_outer_context():
    """Leaving a nested binding restores the previously active context."""
    outer, outer_writer = _context_with_writer()
    inner, inner_writer = _context_with_writer()

    with apix_graph_context(outer):
        assert get_graph_context() is outer
        assert get_stream_writer() is outer_writer
        with apix_graph_context(inner):
            assert get_graph_context() is inner
            assert get_stream_writer() is inner_writer
        assert get_graph_context() is outer
        assert get_stream_writer() is outer_writer


def test_apix_graph_context_resets_after_exception():
    """A failed node-like scope cannot leak its context to later work."""
    context, _ = _context_with_writer()

    with pytest.raises(ValueError, match="failed"):
        with apix_graph_context(context):
            raise ValueError("failed")

    with pytest.raises(RuntimeError, match="only available while a graph context"):
        get_graph_context()


@pytest.mark.asyncio
async def test_apix_graph_context_keeps_concurrent_tasks_isolated():
    """Concurrent tasks retain their own graph context across suspension."""
    left, left_writer = _context_with_writer()
    right, right_writer = _context_with_writer()

    async def observe(context: GraphContext):
        with apix_graph_context(context):
            await asyncio.sleep(0)
            return get_graph_context(), get_stream_writer()

    observed_left, observed_right = await asyncio.gather(
        observe(left),
        observe(right),
    )

    assert observed_left == (left, left_writer)
    assert observed_right == (right, right_writer)
