from contextlib import contextmanager
from collections.abc import Generator
from contextvars import ContextVar

from apix.core.graph.context.graph_context import GraphContext
from apix.core.graph.context.stream_writer import _NOOP_STREAM_WRITER, StreamWriter


_current_graph_context: ContextVar["GraphContext | None"] = ContextVar(
    "apix_graph_context",
    default=None,
)


@contextmanager
def apix_graph_context(context: GraphContext) -> Generator[None, None, None]:
    """Bind a graph context for the duration of one node execution."""
    token = _current_graph_context.set(context)
    try:
        yield
    finally:
        _current_graph_context.reset(token)


def get_current_run_id() -> str:
    """Return the run_id bound to the graph currently being invoked.

    Raises:
        RuntimeError: If called outside a graph invocation context.
    """
    context = _current_graph_context.get()
    if context is None:
        raise RuntimeError(
            "get_current_run_id() is only available while a graph is invoked."
        )

    run_id = context.run_id
    if run_id is None:
        raise RuntimeError(
            "get_current_run_id() is only available while a graph is invoked."
        )
    return run_id


def get_current_namespace() -> str:
    """Return the namespace bound to the graph and context currently being invoked.

    Raises:
        RuntimeError: If called outside a graph invocation context.
    """
    context = _current_graph_context.get()
    if context is None:
        raise RuntimeError(
            "get_current_namespace() is only available while a graph is invoked."
        )

    namespace = context._context_namespace
    if namespace is None:
        raise RuntimeError(
            "get_current_namespace() is only available while a graph is invoked."
        )
    return namespace


def get_stream_writer() -> StreamWriter:
    """Return the writer bound to the graph node currently being executed.

    Raises:
        RuntimeError: If called outside a graph node execution context.
    """
    context = _current_graph_context.get()
    if context is None:
        raise RuntimeError(
            "get_stream_writer() is only available while a graph is invoked."
        )

    writer = context.stream_writer
    if writer is None:
        raise RuntimeError(
            "get_stream_writer() is only available while a graph node is executed."
        )

    if not context.is_active:
        writer = _NOOP_STREAM_WRITER
    return writer


def get_graph_context() -> GraphContext:
    """Return the context bound to the graph currently being invoked.

    Raises:
        RuntimeError: If called outside a graph invocation context.
    """
    context = _current_graph_context.get()
    if context is None:
        raise RuntimeError(
            "get_graph_context() is only available while a graph is invoked."
        )
    return context
