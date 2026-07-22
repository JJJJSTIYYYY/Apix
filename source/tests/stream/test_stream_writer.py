"""Unit tests for the invocation-local stream writer and channel."""

import asyncio

import pytest

from apix.core.stream import StreamWriter, get_stream_writer
from apix.core.stream.stream_writer import (
    StreamChannel,
    noop_stream_writer,
    stream_writer_context,
)


def test_stream_writer_callable_sends_chunk():
    """Calling a writer forwards the chunk to its send callback."""
    chunks = []
    writer = StreamWriter(chunks.append)

    writer({"token": "hello"})

    assert chunks == [{"token": "hello"}]


def test_stream_writer_write_method_sends_chunk():
    """The method-style writer API has the same behaviour as __call__."""
    chunks = []
    writer = StreamWriter(chunks.append)

    writer.write("hello")

    assert chunks == ["hello"]


def test_get_stream_writer_requires_bound_context():
    """Code outside graph node execution cannot access a writer."""
    with pytest.raises(RuntimeError, match="only available while a graph node"):
        get_stream_writer()


def test_stream_writer_context_binds_and_restores_writer():
    """The context manager exposes its writer only inside the context."""
    chunks = []
    writer = StreamWriter(chunks.append)

    with stream_writer_context(writer):
        assert get_stream_writer() is writer
        get_stream_writer()(1)

    assert chunks == [1]
    with pytest.raises(RuntimeError, match="only available while a graph node"):
        get_stream_writer()


def test_nested_stream_writer_context_restores_outer_writer():
    """Leaving a nested context restores the writer that was active before it."""
    outer = StreamWriter(lambda chunk: None)
    inner = StreamWriter(lambda chunk: None)

    with stream_writer_context(outer):
        assert get_stream_writer() is outer
        with stream_writer_context(inner):
            assert get_stream_writer() is inner
        assert get_stream_writer() is outer


def test_stream_writer_context_resets_after_exception():
    """Writer state is cleaned up even when node-like work raises."""
    writer = StreamWriter(lambda chunk: None)

    with pytest.raises(ValueError, match="failed"):
        with stream_writer_context(writer):
            raise ValueError("failed")

    with pytest.raises(RuntimeError, match="only available while a graph node"):
        get_stream_writer()


@pytest.mark.asyncio
async def test_context_var_keeps_concurrent_tasks_isolated():
    """Concurrent tasks retain their own writer across await boundaries."""
    left = StreamWriter(lambda chunk: None)
    right = StreamWriter(lambda chunk: None)

    async def observe(writer):
        with stream_writer_context(writer):
            await asyncio.sleep(0)
            return get_stream_writer()

    observed_left, observed_right = await asyncio.gather(
        observe(left),
        observe(right),
    )

    assert observed_left is left
    assert observed_right is right


def test_noop_stream_writer_is_reusable_and_discards_chunks():
    """Regular graph invocation can write without producing stream output."""
    first = noop_stream_writer()
    second = noop_stream_writer()

    first({"ignored": True})
    second.write("also ignored")

    assert first is second


@pytest.mark.asyncio
async def test_stream_channel_preserves_fifo_order_and_arbitrary_values():
    """Queued chunks are received in write order without type restrictions."""
    channel = StreamChannel()
    payload = object()

    channel.writer({"index": 1})
    channel.writer("second")
    channel.writer(payload)
    channel.close()

    assert channel.__aiter__() is channel
    assert await anext(channel) == {"index": 1}
    assert await anext(channel) == "second"
    assert await anext(channel) is payload
    with pytest.raises(StopAsyncIteration):
        await anext(channel)


@pytest.mark.asyncio
async def test_stream_channel_wakes_waiting_consumer():
    """A writer wakes a consumer already waiting for the next chunk."""
    channel = StreamChannel()
    waiting = asyncio.create_task(anext(channel))
    await asyncio.sleep(0)

    channel.writer("ready")

    assert await waiting == "ready"
    channel.close()


@pytest.mark.asyncio
async def test_stream_channel_close_wakes_waiting_consumer():
    """Closing an empty channel terminates a waiting consumer."""
    channel = StreamChannel()
    waiting = asyncio.create_task(anext(channel))
    await asyncio.sleep(0)

    channel.close()

    with pytest.raises(StopAsyncIteration):
        await waiting


@pytest.mark.asyncio
async def test_stream_channel_close_is_idempotent_and_rejects_late_writes():
    """Closing twice adds one terminator and prevents subsequent writes."""
    channel = StreamChannel()
    channel.close()
    channel.close()

    with pytest.raises(RuntimeError, match="closed graph stream"):
        channel.writer("late")
    with pytest.raises(StopAsyncIteration):
        await anext(channel)


@pytest.mark.asyncio
async def test_stream_channels_do_not_share_messages():
    """Each channel owns an independent queue."""
    left = StreamChannel()
    right = StreamChannel()

    left.writer("left")
    right.writer("right")

    assert await anext(left) == "left"
    assert await anext(right) == "right"
    left.close()
    right.close()