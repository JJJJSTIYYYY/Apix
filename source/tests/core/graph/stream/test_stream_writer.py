"""Unit tests for the invocation-local stream writer and channel."""

import asyncio

import pytest

from apix.core.graph.context import StreamWriter
from apix.core.graph.context.stream_writer import (
    StreamChannel,
    noop_stream_writer,
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
