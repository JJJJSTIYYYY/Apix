"""Exhaustive branch tests for the event channel implementations."""

import asyncio
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from apix.core.event.base import ApixEvent, EventType
from apix.core.event.event_loop import ApixEventLoop
from apix.core.event.event_pipe import (
    ApixEventPipe,
    BaseEventChannel,
    BuiltinChannel,
    EventChannelPermissionError,
    GatewayChannel,
    KafkaChannel,
    RabbitMQChannel,
    UnavailableMailboxChannel,
    _json_default,
    event_from_payload,
    event_to_payload,
)
from apix.core.event.event_registry import ApixEventRegistry
from apix.core.event.event_writer import EventPipeWriter

from .test_event_pipe import FakeClient, make_event, make_gateway, response


class TestSmallUncoveredContracts:
    def test_event_datetime_property(self):
        event = make_event()
        assert event.datetime.timestamp() == pytest.approx(event.timestamp)

    def test_payload_accepts_event_and_rejects_non_mapping(self):
        event = make_event()
        assert event_from_payload(event) is event
        with pytest.raises(TypeError, match="mapping"):
            event_from_payload(42)

    def test_json_default_supports_enum_and_dataclass(self):
        event = make_event()
        assert _json_default(EventType.INFO) == "info"
        assert _json_default(event)["event_id"] == event.event_id
        with pytest.raises(TypeError, match="not JSON serializable"):
            _json_default(object())
        with pytest.raises(TypeError, match="not JSON serializable"):
            _json_default(ApixEvent)

    @pytest.mark.asyncio
    async def test_abstract_method_bodies_raise_not_implemented(self):
        channel = object()
        with pytest.raises(NotImplementedError):
            BaseEventChannel.maxsize.fget(channel)
        with pytest.raises(NotImplementedError):
            await BaseEventChannel.put(channel, "event")
        with pytest.raises(NotImplementedError):
            BaseEventChannel.put_nowait(channel, "event")
        with pytest.raises(NotImplementedError):
            await BaseEventChannel.get(channel)
        with pytest.raises(NotImplementedError):
            BaseEventChannel.get_nowait(channel)
        with pytest.raises(NotImplementedError):
            BaseEventChannel.empty(channel)
        with pytest.raises(NotImplementedError):
            BaseEventChannel.full(channel)
        with pytest.raises(NotImplementedError):
            BaseEventChannel.qsize(channel)
        with pytest.raises(NotImplementedError):
            BaseEventChannel.task_done(channel)
        with pytest.raises(NotImplementedError):
            await BaseEventChannel.join(channel)
        with pytest.raises(NotImplementedError):
            await BaseEventChannel.close(channel)

    def test_writer_task_done_delegates(self, monkeypatch):
        task_done = MagicMock()
        monkeypatch.setattr(
            "apix.core.event.event_writer.EVENT_PIPE.task_done", task_done
        )
        EventPipeWriter().task_done()
        task_done.assert_called_once_with()


class TestBufferedMailboxContract:
    @pytest.mark.asyncio
    async def test_queue_methods_and_write_permissions(self):
        channel = KafkaChannel(
            mq_id="node-a",
            bootstrap_servers="broker:9092",
            topic_prefix="mailbox",
            group_id_prefix="nodes",
            maxsize=1,
        )
        event = make_event()

        assert channel.maxsize == 1
        assert channel.empty() is True
        await channel._enqueue(event_to_payload(event))
        assert channel.full() is True
        assert channel.qsize() == 1
        assert channel.get_nowait().event_id == event.event_id
        channel.task_done()
        await channel.join()

        await channel._enqueue(event)
        assert (await channel.get()).event_id == event.event_id
        channel.task_done()

        with pytest.raises(EventChannelPermissionError, match="receive-only"):
            await channel.put(event)
        with pytest.raises(EventChannelPermissionError, match="receive-only"):
            channel.put_nowait(event)

    @pytest.mark.asyncio
    async def test_unavailable_mailbox_remaining_methods(self):
        channel = UnavailableMailboxChannel("disabled")
        await channel.start()
        with pytest.raises(EventChannelPermissionError, match="receive-only"):
            channel.put_nowait(make_event())
        with pytest.raises(Exception, match="disabled"):
            channel.get_nowait()
        await channel.close()


class FakeKafkaConsumer:
    records = []
    instances = []

    def __init__(self, *topics, **kwargs):
        self.topics = topics
        self.kwargs = kwargs
        self.items = list(type(self).records)
        self.started = False
        self.stopped = False
        type(self).instances.append(self)

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


class BlockingConsumer:
    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.Event().wait()


class TestKafkaChannelLifecycle:
    @pytest.mark.asyncio
    async def test_start_consume_idempotence_and_close(self, monkeypatch):
        event = make_event()
        FakeKafkaConsumer.records = [SimpleNamespace(value=event_to_payload(event))]
        FakeKafkaConsumer.instances.clear()
        monkeypatch.setitem(
            sys.modules,
            "aiokafka",
            SimpleNamespace(AIOKafkaConsumer=FakeKafkaConsumer),
        )
        channel = KafkaChannel(
            mq_id="node-a",
            bootstrap_servers=["broker:9092"],
            topic_prefix="mailbox",
            group_id_prefix="nodes",
        )

        await channel.start()
        await channel._consumer_task
        await channel.start()

        consumer = FakeKafkaConsumer.instances[-1]
        assert consumer.started is True
        assert (await channel.get()).event_id == event.event_id
        channel.task_done()
        await channel.close()
        assert consumer.stopped is True
        assert channel._consumer is None
        await channel.close()

    @pytest.mark.asyncio
    async def test_consumer_cancellation_is_propagated(self):
        channel = KafkaChannel(
            mq_id="node-a",
            bootstrap_servers="broker:9092",
            topic_prefix="mailbox",
            group_id_prefix="nodes",
        )
        channel._consumer = BlockingConsumer()
        task = asyncio.create_task(channel._consume())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class AsyncContext:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value if self.value is not None else self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeMessage:
    def __init__(self, body):
        self.body = body

    def process(self):
        return AsyncContext()


class FakeQueueIterator:
    def __init__(self, messages):
        self.messages = list(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            raise StopAsyncIteration
        return self.messages.pop(0)


class FakeRabbitQueue:
    def __init__(self, messages):
        self.messages = messages
        self.bind_calls = []

    async def bind(self, exchange, routing_key):
        self.bind_calls.append((exchange, routing_key))

    def iterator(self):
        return FakeQueueIterator(self.messages)


class FakeRabbitBrokerChannel:
    def __init__(self, queue):
        self.queue = queue
        self.qos = None
        self.exchange_args = None
        self.queue_args = None
        self.closed = False

    async def set_qos(self, **kwargs):
        self.qos = kwargs

    async def declare_exchange(self, *args, **kwargs):
        self.exchange_args = (args, kwargs)
        return "exchange"

    async def declare_queue(self, *args, **kwargs):
        self.queue_args = (args, kwargs)
        return self.queue

    async def close(self):
        self.closed = True


class FakeRabbitConnection:
    def __init__(self, channel):
        self.broker_channel = channel
        self.closed = False

    async def channel(self):
        return self.broker_channel

    async def close(self):
        self.closed = True


class TestRabbitChannelLifecycle:
    @pytest.mark.asyncio
    async def test_start_consume_idempotence_and_close(self, monkeypatch):
        event = make_event()
        queue = FakeRabbitQueue([FakeMessage(event_to_payload(event))])
        broker_channel = FakeRabbitBrokerChannel(queue)
        connection = FakeRabbitConnection(broker_channel)
        connect = AsyncMock(return_value=connection)
        monkeypatch.setitem(
            sys.modules,
            "aio_pika",
            SimpleNamespace(
                connect_robust=connect,
                ExchangeType=SimpleNamespace(DIRECT="direct"),
            ),
        )
        channel = RabbitMQChannel(
            mq_id="node-a",
            url="amqp://localhost/",
            exchange="events",
            queue_prefix="mailbox",
            prefetch_count=7,
        )

        await channel.start()
        await channel._consumer_task
        await channel.start()

        assert broker_channel.qos == {"prefetch_count": 7}
        assert queue.bind_calls == [("exchange", "node-a")]
        assert (await channel.get()).event_id == event.event_id
        channel.task_done()
        await channel.close()
        assert broker_channel.closed is True
        assert connection.closed is True
        assert channel._broker_queue is None
        await channel.close()


class TestGatewayRemainingBranches:
    @pytest.mark.asyncio
    async def test_owned_client_start_and_close(self, monkeypatch):
        owned = SimpleNamespace(aclose=AsyncMock())
        constructor = lambda **kwargs: owned
        monkeypatch.setattr(
            "apix.core.event.event_pipe.httpx.AsyncClient", constructor
        )
        gateway = GatewayChannel(
            base_url="http://gateway/",
            pipe_endpoint="pipe",
            node_id="node-a",
            node_name="Alice",
            channel_type="kafka",
            max_retry=0,
            retry_initial_delay=0,
            timeout=3,
        )
        assert gateway.maxsize == 0
        await gateway.start()
        await gateway.start()
        await gateway.close()
        owned.aclose.assert_awaited_once_with()
        await gateway.close()

    @pytest.mark.asyncio
    async def test_final_request_error_and_empty_retry_range(self):
        request = httpx.Request("POST", "http://gateway/api/pipe")
        gateway = make_gateway(
            FakeClient([httpx.ConnectError("offline", request=request)])
        )
        gateway.max_retry = 0
        with pytest.raises(httpx.ConnectError):
            await gateway.put(make_event(), recipient="node-b")

        gateway.max_retry = -1
        with pytest.raises(AssertionError, match="retry loop"):
            await gateway._request("GET")

    @pytest.mark.asyncio
    async def test_broadcast_json_variants(self):
        empty = httpx.Response(
            204,
            request=httpx.Request("POST", "http://gateway/api/pipe"),
        )
        gateway = make_gateway(FakeClient([empty, response(200, ["not", "dict"])]))
        assert await gateway.broadcast(make_event()) == {}
        assert await gateway.broadcast(make_event()) == {}

    @pytest.mark.asyncio
    async def test_fetch_nodes_all_payload_shapes(self):
        empty = httpx.Response(
            204,
            request=httpx.Request("GET", "http://gateway/api/pipe"),
        )
        gateway = make_gateway(
            FakeClient(
                [
                    empty,
                    response(
                        200,
                        {
                            "node-a": {"tag": "A"},
                            "invalid": "value",
                        },
                    ),
                    response(
                        200,
                        [
                            {"node_id": "node-b", "tag": "B"},
                            {"tag": "missing-id"},
                            "invalid",
                        ],
                    ),
                    response(200, "invalid"),
                ]
            )
        )
        assert await gateway.fetch_nodes() == {}
        assert await gateway.fetch_nodes() == {"node-a": {"tag": "A"}}
        assert await gateway.fetch_nodes() == {
            "node-b": {"node_id": "node-b", "tag": "B"}
        }
        assert await gateway.fetch_nodes() == {}

    @pytest.mark.asyncio
    async def test_all_write_only_operations_raise(self):
        gateway = make_gateway(FakeClient([]))
        with pytest.raises(EventChannelPermissionError):
            gateway.put_nowait(make_event())
        with pytest.raises(EventChannelPermissionError):
            await gateway.get()
        with pytest.raises(EventChannelPermissionError):
            gateway.get_nowait()
        with pytest.raises(EventChannelPermissionError):
            gateway.empty()
        with pytest.raises(EventChannelPermissionError):
            gateway.full()
        with pytest.raises(EventChannelPermissionError):
            gateway.qsize()
        with pytest.raises(EventChannelPermissionError):
            gateway.task_done()
        with pytest.raises(EventChannelPermissionError):
            await gateway.join()


class BroadcastOnlyChannel(BuiltinChannel):
    def __init__(self, result=None, error=None):
        super().__init__()
        self.result = {} if result is None else result
        self.error = error
        self.broadcasts = []

    async def broadcast(self, event):
        self.broadcasts.append(event)
        if self.error is not None:
            raise self.error
        return self.result


class CloseErrorChannel(BuiltinChannel):
    async def close(self):
        raise RuntimeError("close failed")


class TestApixEventPipeRemainingBranches:
    def test_builds_each_mailbox_type_and_rejects_unknown(self):
        kafka = ApixEventPipe(remote_enabled=True, channel_type="kafka")
        rabbit = ApixEventPipe(remote_enabled=True, channel_type="rabbitmq")
        assert isinstance(kafka.get_channel("mailbox"), KafkaChannel)
        assert isinstance(rabbit.get_channel("mailbox"), RabbitMQChannel)
        with pytest.raises(ValueError, match="EVENT_CHANNEL.type"):
            ApixEventPipe(remote_enabled=True, channel_type="invalid")

    @pytest.mark.asyncio
    async def test_queue_delegates_and_remote_send(self):
        gateway = make_gateway(FakeClient([response()]))
        pipe = ApixEventPipe(remote_enabled=False, mailtruck=gateway)

        pipe.put_nowait("local")
        assert pipe.full() is False
        assert pipe.get_nowait() == "local"
        pipe.task_done()
        await pipe.join()

        with pytest.raises(EventChannelPermissionError):
            pipe.put_nowait(make_event(), "mailbox")
        with pytest.raises(EventChannelPermissionError):
            pipe.put_nowait(make_event(), "mailtruck")
        with pytest.raises(EventChannelPermissionError):
            pipe.get_nowait("mailtruck")

        await pipe.send(make_event(), "node-b")

    @pytest.mark.asyncio
    async def test_broadcast_requires_capable_mailtruck(self):
        pipe = ApixEventPipe(
            remote_enabled=True,
            mailbox=BuiltinChannel(),
            mailtruck=BuiltinChannel(),
        )
        with pytest.raises(TypeError, match="broadcast"):
            await pipe.broadcast(make_event())

    def test_update_nodes_handles_all_shapes_and_returns_copy(self):
        pipe = ApixEventPipe(remote_enabled=False)
        pipe._update_nodes(
            {
                "nodes": {
                    "fallback-id": {"tag": "A"},
                    "ignored": "invalid",
                }
            }
        )
        pipe._update_nodes(
            [
                {"node_id": "node-b", "tag": "B"},
                {"tag": "missing"},
                "invalid",
            ]
        )
        pipe._update_nodes("invalid")
        snapshot = pipe.nodes
        snapshot["fallback-id"]["tag"] = "changed"
        assert pipe.nodes["fallback-id"]["tag"] == "A"
        assert pipe.nodes["node-b"]["tag"] == "B"

    @pytest.mark.asyncio
    async def test_local_start_is_idempotent_and_stop_is_idempotent(self):
        pipe = ApixEventPipe(remote_enabled=False)
        await pipe.start()
        await pipe.start()
        await pipe.stop()
        await pipe.stop()

    @pytest.mark.asyncio
    async def test_start_without_fetch_nodes_and_broadcast_updates_nodes(self):
        mailtruck = BroadcastOnlyChannel(
            {"nodes": {"node-b": {"tag": "B", "status": "ok"}}}
        )
        pipe = ApixEventPipe(
            remote_enabled=True,
            mailbox=BuiltinChannel(),
            mailtruck=mailtruck,
        )
        await pipe.start()
        assert pipe.nodes["node-b"]["status"] == "ok"
        await pipe.stop()

    @pytest.mark.asyncio
    async def test_start_failure_closes_channels_and_reraises(self):
        mailtruck = BroadcastOnlyChannel(error=RuntimeError("broadcast failed"))
        pipe = ApixEventPipe(
            remote_enabled=True,
            mailbox=BuiltinChannel(),
            mailtruck=mailtruck,
        )
        with pytest.raises(RuntimeError, match="broadcast failed"):
            await pipe.start()
        assert pipe._mailbox_forwarder is None

    @pytest.mark.asyncio
    async def test_close_collects_forwarder_and_channel_errors(self):
        pipe = ApixEventPipe(
            remote_enabled=False,
            mailbox=CloseErrorChannel(),
        )

        async def fail():
            raise ValueError("forwarder failed")

        pipe._mailbox_forwarder = asyncio.create_task(fail())
        await asyncio.sleep(0)
        errors = await pipe._close_channels()
        assert {str(error) for error in errors} == {
            "forwarder failed",
            "close failed",
        }

    @pytest.mark.asyncio
    async def test_stop_collects_broadcast_error_and_raises(self):
        pipe = ApixEventPipe(
            remote_enabled=True,
            mailbox=BuiltinChannel(),
            mailtruck=BroadcastOnlyChannel(
                error=RuntimeError("offline broadcast failed")
            ),
        )
        pipe._started = True
        with pytest.raises(RuntimeError, match="offline broadcast failed"):
            await pipe.stop()
        assert pipe._started is False

    @pytest.mark.asyncio
    async def test_stop_raises_close_error(self):
        pipe = ApixEventPipe(
            remote_enabled=False,
            mailbox=CloseErrorChannel(),
        )
        pipe._started = True
        with pytest.raises(RuntimeError, match="close failed"):
            await pipe.stop()


class TestEventLoopRemainingBranches:
    @pytest.mark.asyncio
    async def test_real_consumer_loop_dispatches_and_handles_cancellation(
        self, monkeypatch
    ):
        registry = ApixEventRegistry()
        registry._handlers.clear()
        handler = ApixEventLoop(registry)
        event = make_event()
        get_event = AsyncMock(side_effect=[event, asyncio.CancelledError()])
        dispatch = AsyncMock()
        monkeypatch.setattr(
            "apix.core.event.event_loop.event_pipe_writer.get_event", get_event
        )
        monkeypatch.setattr(handler, "_dispatch_event_and_ack", dispatch)

        await handler._event_consumer_loop()
        await asyncio.gather(*handler._dispatch_tasks)
        dispatch.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_consumer_releases_semaphore_when_get_fails(self, monkeypatch):
        registry = ApixEventRegistry()
        registry._handlers.clear()
        handler = ApixEventLoop(registry)
        initial_value = handler._dispatch_semaphore._value
        monkeypatch.setattr(
            "apix.core.event.event_loop.event_pipe_writer.get_event",
            AsyncMock(side_effect=RuntimeError("get failed")),
        )
        with pytest.raises(RuntimeError, match="get failed"):
            await handler._event_consumer_loop()
        assert handler._dispatch_semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_dispatch_without_timeout(self):
        registry = ApixEventRegistry()
        registry._handlers.clear()
        handler = ApixEventLoop(registry)
        callback = AsyncMock()
        from apix.core.event.base import HandlerEntry

        registry._handlers["test.event"] = [
            HandlerEntry(
                id="handler-1",
                name="handler",
                subscribe="test.event",
                callback=callback,
                priority=1,
                register_order=0,
                time_out=-1,
            )
        ]
        event = make_event()
        await handler._dispatch_event(event)
        callback.assert_awaited_once_with(event)
