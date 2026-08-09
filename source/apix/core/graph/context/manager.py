from contextlib import contextmanager
from typing import Generator
from contextvars import ContextVar

from apix.core.graph.context.graph_context import GraphContext
from apix.core.graph.context.stream_writer import StreamWriter


_current_graph_context: ContextVar["GraphContext | None"] = ContextVar(
    "apix_graph_context",
    default=None,
)


@contextmanager
def apix_graph_context(context: GraphContext) -> Generator[None]:
    """Bind a writer for the duration of one node execution."""
    token = _current_graph_context.set(context)
    try:
        yield
    finally:
        _current_graph_context.reset(token)


def get_stream_writer() -> StreamWriter:
    """Return the writer bound to the graph node currently being executed.

    Raises:
        RuntimeError: If called outside a graph node execution context.
    """
    context = _current_graph_context.get()
    if context is None:
        raise RuntimeError(
            "get_stream_writer() is only available while a graph context is bound."
        )

    writer = context.stream_writer
    if writer is None:
        raise RuntimeError(
            "get_stream_writer() is only available while a graph node is running."
        )
    return writer


def get_graph_context() -> GraphContext:
    """Return the context bound to the graph node currently being executed.

    Raises:
        RuntimeError: If called outside a graph node execution context.
    """
    context = _current_graph_context.get()
    if context is None:
        raise RuntimeError(
            "get_graph_context() is only available while a graph context is bound."
        )
    return context
