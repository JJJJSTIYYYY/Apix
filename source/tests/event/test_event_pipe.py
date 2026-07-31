"""Tests for queue compatibility and node-side event routing."""

import asyncio
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from apix.core.event.base import ApixEvent, EventType
from apix.core.event.event_pipe import (
    EVENT_PIPE,
    ApixEventPipe,
    BuiltinChannel,
    EventChannelPermissionError,
    EventChannelUnavailableError,
    GatewayChannel,
    KafkaChannel,
    RabbitMQChannel,
    encode_event,
    event_from_payload,
    event_to_payload,
)


def make_event(name: str = "test.event") -> ApixEvent:
    return ApixEvent(
        event_id="event-1",
        event_type=EventType.INFO,
        event_name=name,
        context={"value": 1},
        timestamp=time.time(),
        accepted=False,
    )


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.closed = False

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def aclose(self):
        self.closed = True


def response(status: int = 200, payload=None) -> httpx.Response:
    return httpx.Response(
        status,
        request=httpx.Request("GET", "http://gateway/api/pipe"),
        json={} if payload is None else payload,
    )


def make_gateway(client) -> GatewayChannel:
    return GatewayChannel(
        base_url="http://gateway",
        pipe_endpoint="/api/pipe",
        node_id="node-a",
        node_name="Alice",
        channel_type="kafka",
        max_retry=2,
        retry_initial_delay=0.1,
        timeout=1,
        client=client,
    )


class TestBuiltinChannel:
    @pytest.mark.asyncio
    async def test_queue_compatible_methods(self):
        channel = BuiltinChannel(maxsize=2)

        await channel.put("first")
        channel.put_nowait("second")

        assert channel.maxsize == 2
        assert channel.qsize() == 2
        assert channel.full() is True
        assert await channel.get() == "first"
        assert channel.get_nowait() == "second"
        channel.task_done()
        channel.task_done()
        await asyncio.wait_for(channel.join(), timeout=0.1)
        assert channel.empty() is True

    @pytest.mark.asyncio
    async def test_global_pipe_is_apix_event_pipe_singleton(self):
        from apix.core.event.event_pipe import EVENT_PIPE as second_import

        assert isinstance(EVENT_PIPE, ApixEventPipe)
        assert EVENT_PIPE is second_import
        assert EVENT_PIPE.maxsize > 0

        while not EVENT_PIPE.empty():
            EVENT_PIPE.get_nowait()
            EVENT_PIPE.task_done()
        await EVENT_PIPE.put("event")
        assert await EVENT_PIPE.get() == "event"
        EVENT_PIPE.task_done()


class TestSerialization:
    def test_event_round_trip(self):
        event = make_event()
        restored = event_from_payload(encode_event(event))

        assert event_to_payload(restored) == event_to_payload(event)

    def test_gateway_envelope_is_accepted(self):
        restored = event_from_payload({"recipient": "node-a", "event": event_to_payload(make_event())})
        assert restored.event_name == "test.event"

    def test_invalid_external_event_is_rejected(self):
        with pytest.raises(TypeError, match="ApixEvent"):
            event_to_payload("not-an-event")
        with pytest.raises(ValueError, match="missing fields"):
            event_from_payload({"event_name": "missing"})


class TestExternalChannels:
    def test_kafka_uses_node_id_for_topic_and_group(self):
        channel = KafkaChannel(
            mq_id="node-a",
            bootstrap_servers=["broker:9092"],
            topic_prefix="mailbox",
            group_id_prefix="nodes",
        )
        assert channel.mq_id == "node-a"
        assert channel.topic == "mailbox.node-a"
        assert channel.group_id == "nodes.node-a"

    def test_rabbitmq_uses_node_id_for_queue(self):
        channel = RabbitMQChannel(
            mq_id="node-a",
            url="amqp://localhost/",
            exchange="events",
            queue_prefix="mailbox",
            prefetch_count=5,
        )
        assert channel.mq_id == "node-a"
        assert channel.queue_name == "mailbox.node-a"

    @pytest.mark.asyncio
    async def test_mailbox_rejects_push_and_disabled_mailbox_rejects_get(self):
        pipe = ApixEventPipe(remote_enabled=False)
        with pytest.raises(EventChannelPermissionError, match="receive-only"):
            await pipe.put(make_event(), "mailbox")
        with pytest.raises(EventChannelUnavailableError, match="disabled"):
            await pipe.get("mailbox")

    @pytest.mark.asyncio
    async def test_mailtruck_rejects_read(self):
        pipe = ApixEventPipe(remote_enabled=False)
        with pytest.raises(EventChannelPermissionError, match="write-only"):
            await pipe.get("mailtruck")
        with pytest.raises(EventChannelPermissionError, match="write-only"):
            pipe.qsize("mailtruck")

    def test_unknown_channel_is_rejected(self):
        pipe = ApixEventPipe(remote_enabled=False)
        with pytest.raises(ValueError, match="Unknown event channel"):
            pipe.get_channel("missing")


class TestGatewayChannel:
    @pytest.mark.asyncio
    async def test_route_protocol_contains_sender_recipient_and_event(self):
        client = FakeClient([response()])
        gateway = make_gateway(client)

        await gateway.put(make_event(), recipient="node-b")

        method, url, kwargs = client.requests[0]
        assert method == "POST"
        assert url == "http://gateway/api/pipe"
        assert kwargs["json"]["action"] == "route"
        assert kwargs["json"]["sender"] == {
            "tag": "Alice",
            "node_id": "node-a",
            "channel_type": "kafka",
        }
        assert kwargs["json"]["recipient"] == "node-b"
        assert kwargs["json"]["event"]["event_name"] == "test.event"

    @pytest.mark.asyncio
    async def test_route_requires_recipient(self):
        gateway = make_gateway(FakeClient([]))
        with pytest.raises(ValueError, match="recipient mq_id"):
            await gateway.put(make_event())

    @pytest.mark.asyncio
    async def test_503_uses_exponential_backoff(self, monkeypatch):
        client = FakeClient([response(503), response(503), response(200)])
        gateway = make_gateway(client)
        sleep = AsyncMock()
        monkeypatch.setattr("apix.core.event.event_pipe.asyncio.sleep", sleep)

        await gateway.put(make_event(), recipient="node-b")

        assert len(client.requests) == 3
        assert [call.args[0] for call in sleep.await_args_list] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_503_raises_after_max_retries(self, monkeypatch):
        client = FakeClient([response(503), response(503), response(503)])
        gateway = make_gateway(client)
        monkeypatch.setattr(
            "apix.core.event.event_pipe.asyncio.sleep", AsyncMock()
        )

        with pytest.raises(httpx.HTTPStatusError):
            await gateway.put(make_event(), recipient="node-b")
        assert len(client.requests) == 3

    @pytest.mark.asyncio
    async def test_request_error_is_retried(self, monkeypatch):
        request = httpx.Request("POST", "http://gateway/api/pipe")
        client = FakeClient(
            [httpx.ConnectError("offline", request=request), response(200)]
        )
        gateway = make_gateway(client)
        sleep = AsyncMock()
        monkeypatch.setattr("apix.core.event.event_pipe.asyncio.sleep", sleep)

        await gateway.put(make_event(), recipient="node-b")
        sleep.assert_awaited_once_with(0.1)

    @pytest.mark.asyncio
    async def test_fetch_nodes_normalises_list(self):
        gateway = make_gateway(
            FakeClient(
                [response(200, {"nodes": [{"tag": "B", "node_id": "node-b", "status": "ok"}]})]
            )
        )
        assert await gateway.fetch_nodes() == {
            "node-b": {"tag": "B", "node_id": "node-b", "status": "ok"}
        }


class TestApixEventPipeLifecycle:
    @pytest.mark.asyncio
    async def test_mailbox_events_are_forwarded_to_builtin(self):
        mailbox = BuiltinChannel(maxsize=2)
        builtin = BuiltinChannel(maxsize=2)
        pipe = ApixEventPipe(
            remote_enabled=True,
            builtin=builtin,
            mailbox=mailbox,
            mailtruck=make_gateway(FakeClient([response(), response(), response()])),
            mq_id="node-a",
            node_name="Alice",
        )

        await pipe.start()
        event = make_event("remote.event")
        await mailbox.put(event)

        assert await asyncio.wait_for(pipe.get(), timeout=0.1) is event
        pipe.task_done()
        await pipe.stop()

    @pytest.mark.asyncio
    async def test_start_broadcasts_then_fetches_and_stop_broadcasts(self):
        client = FakeClient(
            [
                response(200),
                response(200, {"nodes": [{"tag": "B", "node_id": "node-b", "status": "ok"}]}),
                response(200),
            ]
        )
        pipe = ApixEventPipe(
            remote_enabled=True,
            builtin=BuiltinChannel(),
            mailbox=BuiltinChannel(),
            mailtruck=make_gateway(client),
            mq_id="node-a",
            node_name="Alice",
        )

        await pipe.start()
        assert pipe.nodes["node-b"]["status"] == "ok"
        await pipe.stop()

        assert [entry[0] for entry in client.requests] == ["POST", "GET", "POST"]
        assert client.requests[0][2]["json"]["event"]["event_name"] == "apix.node.online"
        assert client.requests[2][2]["json"]["event"]["event_name"] == "apix.node.offline"

    @pytest.mark.asyncio
    async def test_disabled_lifecycle_does_not_contact_gateway(self):
        client = FakeClient([])
        pipe = ApixEventPipe(
            remote_enabled=False,
            mailtruck=make_gateway(client),
        )
        await pipe.start()
        assert await pipe.broadcast(make_event()) == {}
        await pipe.stop()
        assert client.requests == []
