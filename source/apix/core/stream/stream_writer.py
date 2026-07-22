"""Invocation-local message queue and writer for graph streaming."""

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


_STREAM_END = object()
_current_stream_writer: ContextVar["StreamWriter | None"] = ContextVar(
    "apix_stream_writer",
    default=None,
)


class StreamWriter:
    """Synchronous callable used by a node to emit a custom stream chunk."""

    def __init__(self, send: Callable[[Any], None]):
        """Create a writer backed by the supplied synchronous send callback."""
        self._send = send

    def __call__(self, chunk: Any) -> None:
        """Emit one chunk to the current graph stream."""
        self._send(chunk)

    def write(self, chunk: Any) -> None:
        """Emit one chunk using a method-style API."""
        self(chunk)


class StreamChannel(AsyncIterator[Any]):
    """Single-consumer asynchronous queue for one graph stream invocation."""

    def __init__(self):
        """Create an open channel and its node-facing writer."""
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._closed = False
        self.writer = StreamWriter(self._send)

    def _send(self, chunk: Any) -> None:
        """Append a chunk without blocking the node currently executing."""
        if self._closed:
            raise RuntimeError("Cannot write to a closed graph stream.")
        self._queue.put_nowait(chunk)

    def close(self) -> None:
        """Finish the channel after all already queued chunks are consumed."""
        if not self._closed:
            self._closed = True
            self._queue.put_nowait(_STREAM_END)

    def __aiter__(self) -> "StreamChannel":
        return self

    async def __anext__(self) -> Any:
        chunk = await self._queue.get()
        if chunk is _STREAM_END:
            raise StopAsyncIteration
        return chunk


def get_stream_writer() -> StreamWriter:
    """Return the writer bound to the graph node currently being executed.

    Raises:
        RuntimeError: If called outside a graph node execution context.
    """
    writer = _current_stream_writer.get()
    if writer is None:
        raise RuntimeError(
            "get_stream_writer() is only available while a graph node is running."
        )
    return writer


@contextmanager
def stream_writer_context(writer: StreamWriter) -> Iterator[None]:
    """Bind a writer for the duration of one node execution."""
    token = _current_stream_writer.set(writer)
    try:
        yield
    finally:
        _current_stream_writer.reset(token)


_NOOP_STREAM_WRITER = StreamWriter(lambda chunk: None)


def noop_stream_writer() -> StreamWriter:
    """Return the writer used by non-streaming graph invocations."""
    return _NOOP_STREAM_WRITER
