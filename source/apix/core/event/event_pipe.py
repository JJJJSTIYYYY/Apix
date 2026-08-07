"""Event channels and the node-side event pipe.

``ApixEventPipe`` keeps local event dispatch on an :class:`asyncio.Queue` while
isolating all external transport details behind mailbox and mailtruck
channels.  The event registry therefore only consumes the builtin channel and
does not need to know whether an event originated locally, from Kafka, or from
RabbitMQ.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

import httpx

from apix.core.utils.exception import EventChannelPermissionError, EventChannelUnavailableError
from apix.config.base_config import (
    EVENT_CHANNEL_CONFIG,
    EVENT_CHANNEL_TYPE,
    EVENT_PIPE_MAX_LEN,
    GATEWAY_MAX_RETRY,
    GATEWAY_RETRY_INITIAL_DELAY,
    GATEWAY_TIMEOUT,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_GROUP_ID_PREFIX,
    KAFKA_TOPIC_PREFIX,
    NODE_ID,
    NODE_NAME,
    RABBITMQ_EXCHANGE,
    RABBITMQ_PREFETCH_COUNT,
    RABBITMQ_QUEUE_PREFIX,
    RABBITMQ_URL,
    REMOTE_GATEWAY_BASE_URL,
    REMOTE_GATEWAY_ENABLE,
    REMOTE_GATEWAY_PIPE_ENDPOINT,
)
from apix.core.event.base import ApixEvent, ChannelName, EventType


def event_to_payload(event: ApixEvent) -> dict[str, Any]:
    """Convert an :class:`ApixEvent` to its wire representation."""
    if not isinstance(event, ApixEvent):
        raise TypeError(
            "External event channels only accept ApixEvent instances, "
            f"got {type(event).__name__}."
        )
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "event_name": event.event_name,
        "context": event.context,
        "timestamp": event.timestamp,
        "accepted": event.accepted,
    }


def event_from_payload(payload: Any) -> ApixEvent:
    """Deserialize a broker or gateway payload into an :class:`ApixEvent`."""
    if isinstance(payload, ApixEvent):
        return payload
    if isinstance(payload, (bytes, bytearray, memoryview)):
        payload = bytes(payload).decode("utf-8")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, Mapping):
        raise TypeError(
            "External event payload must be a mapping, JSON string, or bytes."
        )

    # A gateway may retain its routing envelope when publishing to a mailbox.
    if isinstance(payload.get("event"), Mapping):
        payload = payload["event"]

    required = {"event_id", "event_type", "event_name", "timestamp"}
    missing = required.difference(payload)
    if missing:
        raise ValueError(
            "External event payload is missing fields: "
            + ", ".join(sorted(missing))
        )
    return ApixEvent(
        event_id=str(payload["event_id"]),
        event_type=EventType(payload["event_type"]),
        event_name=str(payload["event_name"]),
        context=payload.get("context"),
        timestamp=float(payload["timestamp"]),
        accepted=bool(payload.get("accepted", False)),
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def encode_event(event: ApixEvent) -> bytes:
    """Encode an event for Kafka or RabbitMQ."""
    return json.dumps(
        event_to_payload(event),
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


class BaseEventChannel(ABC):
    """Queue-like interface shared by builtin and external event channels."""

    @property
    @abstractmethod
    def maxsize(self) -> int:
        """Maximum buffered event count. Zero means unbounded."""
        raise NotImplementedError

    async def start(self) -> None:
        """Open connections and start background consumers when required."""

    @abstractmethod
    async def put(self, event: Any, **kwargs: Any) -> None:
        """Push an event, waiting for capacity when necessary."""
        raise NotImplementedError

    @abstractmethod
    def put_nowait(self, event: Any) -> None:
        """Push an event without waiting."""
        raise NotImplementedError

    @abstractmethod
    async def get(self) -> Any:
        """Wait for and retrieve an event."""
        raise NotImplementedError

    @abstractmethod
    def get_nowait(self) -> Any:
        """Retrieve an event without waiting."""
        raise NotImplementedError

    @abstractmethod
    def empty(self) -> bool:
        """Return whether no buffered event is available."""
        raise NotImplementedError

    @abstractmethod
    def full(self) -> bool:
        """Return whether the local buffer is full."""
        raise NotImplementedError

    @abstractmethod
    def qsize(self) -> int:
        """Return the local buffered event count."""
        raise NotImplementedError

    @abstractmethod
    def task_done(self) -> None:
        """Mark a retrieved event as processed."""
        raise NotImplementedError

    @abstractmethod
    async def join(self) -> None:
        """Wait until all retrieved events have been processed."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release connections and background tasks."""
        raise NotImplementedError


class BuiltinChannel(BaseEventChannel):
    """In-process event channel backed by :class:`asyncio.Queue`."""

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)

    @property
    def maxsize(self) -> int:
        return self._queue.maxsize

    async def put(self, event: Any, **kwargs: Any) -> None:
        await self._queue.put(event)

    def put_nowait(self, event: Any) -> None:
        self._queue.put_nowait(event)

    async def get(self) -> Any:
        return await self._queue.get()

    def get_nowait(self) -> Any:
        return self._queue.get_nowait()

    def empty(self) -> bool:
        return self._queue.empty()

    def full(self) -> bool:
        return self._queue.full()

    def qsize(self) -> int:
        return self._queue.qsize()

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    async def close(self) -> None:
        return None


class _BufferedMailboxChannel(BaseEventChannel):
    """Common local-buffer behaviour for receive-only broker channels."""

    def __init__(self, maxsize: int) -> None:
        self._buffer: asyncio.Queue[ApixEvent] = asyncio.Queue(maxsize=maxsize)

    @property
    def maxsize(self) -> int:
        return self._buffer.maxsize

    async def _enqueue(self, payload: Any) -> None:
        await self._buffer.put(event_from_payload(payload))

    async def put(self, event: Any, **kwargs: Any) -> None:
        raise EventChannelPermissionError("mailbox channels are receive-only")

    def put_nowait(self, event: Any) -> None:
        raise EventChannelPermissionError("mailbox channels are receive-only")

    async def get(self) -> ApixEvent:
        return await self._buffer.get()

    def get_nowait(self) -> ApixEvent:
        return self._buffer.get_nowait()

    def empty(self) -> bool:
        return self._buffer.empty()

    def full(self) -> bool:
        return self._buffer.full()

    def qsize(self) -> int:
        return self._buffer.qsize()

    def task_done(self) -> None:
        self._buffer.task_done()

    async def join(self) -> None:
        await self._buffer.join()


class KafkaChannel(_BufferedMailboxChannel):
    """Kafka mailbox consumer.  ``aiokafka`` is imported only when started."""

    def __init__(
        self,
        *,
        mq_id: str,
        bootstrap_servers: str | list[str],
        topic_prefix: str,
        group_id_prefix: str,
        maxsize: int = EVENT_PIPE_MAX_LEN,
    ) -> None:
        super().__init__(maxsize)
        self.mq_id = mq_id
        self.topic = f"{topic_prefix}.{mq_id}"
        self.group_id = f"{group_id_prefix}.{mq_id}"
        self.bootstrap_servers = bootstrap_servers
        self._consumer: Any = None
        self._consumer_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._consumer is not None:
            return
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise EventChannelUnavailableError(
                "Kafka mailbox requires the `aiokafka` package. Run `uv add aiokafka` to install."
            ) from exc

        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            enable_auto_commit=True,
            auto_offset_reset="latest",
        )
        await self._consumer.start()
        self._consumer_task = asyncio.create_task(
            self._consume(), name=f"kafka-mailbox-{self.mq_id}"
        )

    async def _consume(self) -> None:
        try:
            async for record in self._consumer:
                await self._enqueue(record.value)
        except asyncio.CancelledError:
            raise

    async def close(self) -> None:
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer_task
            self._consumer_task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None


class RabbitMQChannel(_BufferedMailboxChannel):
    """RabbitMQ mailbox consumer.  ``aio-pika`` is imported when started."""

    def __init__(
        self,
        *,
        mq_id: str,
        url: str,
        exchange: str,
        queue_prefix: str,
        prefetch_count: int,
        maxsize: int = EVENT_PIPE_MAX_LEN,
    ) -> None:
        super().__init__(maxsize)
        self.mq_id = mq_id
        self.url = url
        self.exchange_name = exchange
        self.queue_name = f"{queue_prefix}.{mq_id}"
        self.prefetch_count = prefetch_count
        self._connection: Any = None
        self._broker_channel: Any = None
        self._broker_queue: Any = None
        self._consumer_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._connection is not None:
            return
        try:
            import aio_pika
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise EventChannelUnavailableError(
                "RabbitMQ mailbox requires the `aio-pika` package. Run `uv add aio-pika` to install."
            ) from exc

        self._connection = await aio_pika.connect_robust(self.url)
        self._broker_channel = await self._connection.channel()
        await self._broker_channel.set_qos(prefetch_count=self.prefetch_count)
        exchange = await self._broker_channel.declare_exchange(
            self.exchange_name,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        self._broker_queue = await self._broker_channel.declare_queue(
            self.queue_name,
            durable=True,
        )
        await self._broker_queue.bind(exchange, routing_key=self.mq_id)
        self._consumer_task = asyncio.create_task(
            self._consume(), name=f"rabbitmq-mailbox-{self.mq_id}"
        )

    async def _consume(self) -> None:
        async with self._broker_queue.iterator() as iterator:
            async for message in iterator:
                async with message.process():
                    await self._enqueue(message.body)

    async def close(self) -> None:
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer_task
            self._consumer_task = None
        if self._broker_channel is not None:
            await self._broker_channel.close()
            self._broker_channel = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
        self._broker_queue = None


class UnavailableMailboxChannel(_BufferedMailboxChannel):
    """Placeholder used when remote gateway mode is disabled."""

    def __init__(self, reason: str, maxsize: int = EVENT_PIPE_MAX_LEN) -> None:
        super().__init__(maxsize)
        self.reason = reason

    async def start(self) -> None:
        return None

    async def get(self) -> ApixEvent:
        raise EventChannelUnavailableError(self.reason)

    def get_nowait(self) -> ApixEvent:
        raise EventChannelUnavailableError(self.reason)

    async def close(self) -> None:
        return None


class GatewayChannel(BaseEventChannel):
    """Write-only HTTP channel used to ask the gateway to route events."""

    def __init__(
        self,
        *,
        base_url: str,
        pipe_endpoint: str,
        node_id: str,
        node_name: str,
        channel_type: str,
        max_retry: int,
        retry_initial_delay: float,
        timeout: float,
        client: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.pipe_endpoint = "/" + pipe_endpoint.lstrip("/")
        self.node_id = node_id
        self.node_name = node_name
        self.channel_type = channel_type
        self.max_retry = max_retry
        self.retry_initial_delay = retry_initial_delay
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def maxsize(self) -> int:
        return 0

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.pipe_endpoint}"

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)

    async def _request(self, method: str, **kwargs: Any) -> httpx.Response:
        await self.start()
        assert self._client is not None

        for retry in range(self.max_retry + 1):
            try:
                response = await self._client.request(method, self.url, **kwargs)
            except httpx.RequestError:
                if retry >= self.max_retry:
                    raise
            else:
                if response.status_code != 503:
                    response.raise_for_status()
                    return response
                if retry >= self.max_retry:
                    response.raise_for_status()

            await asyncio.sleep(self.retry_initial_delay * (2**retry))

        raise AssertionError("gateway retry loop ended unexpectedly")

    def _sender(self) -> dict[str, str]:
        return {
            "tag": self.node_name,
            "node_id": self.node_id,
            "channel_type": self.channel_type,
        }

    async def put(self, event: Any, **kwargs: Any) -> None:
        recipient = kwargs.get("recipient")
        if not isinstance(recipient, str) or not recipient.strip():
            raise ValueError("mailtruck requires a non-empty recipient mq_id")
        await self._request(
            "POST",
            json={
                "action": "route",
                "sender": self._sender(),
                "recipient": recipient,
                "event": event_to_payload(event),
            },
        )

    async def broadcast(self, event: ApixEvent) -> dict[str, Any]:
        response = await self._request(
            "POST",
            json={
                "action": "broadcast",
                "sender": self._sender(),
                "event": event_to_payload(event),
            },
        )
        try:
            data = response.json()
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    async def fetch_nodes(self) -> dict[str, dict[str, Any]]:
        response = await self._request(
            "GET",
            params={"action": "nodes", "node_id": self.node_id},
        )
        try:
            data = response.json()
        except json.JSONDecodeError:
            return {}
        if isinstance(data, Mapping):
            data = data.get("nodes", data)

        nodes: dict[str, dict[str, Any]] = {}
        if isinstance(data, Mapping):
            for key, value in data.items():
                if isinstance(value, Mapping):
                    node = dict(value)
                    mq_id = str(node.get("node_id", key))
                    nodes[mq_id] = node
        elif isinstance(data, list):
            for value in data:
                if isinstance(value, Mapping) and value.get("node_id"):
                    node = dict(value)
                    nodes[str(node["node_id"])] = node
        return nodes

    def put_nowait(self, event: Any) -> None:
        raise EventChannelPermissionError(
            "mailtruck performs asynchronous HTTP writes; use await put()"
        )

    async def get(self) -> Any:
        raise EventChannelPermissionError("mailtruck channels are write-only")

    def get_nowait(self) -> Any:
        raise EventChannelPermissionError("mailtruck channels are write-only")

    def empty(self) -> bool:
        raise EventChannelPermissionError("mailtruck channels are write-only")

    def full(self) -> bool:
        raise EventChannelPermissionError("mailtruck channels are write-only")

    def qsize(self) -> int:
        raise EventChannelPermissionError("mailtruck channels are write-only")

    def task_done(self) -> None:
        raise EventChannelPermissionError("mailtruck channels are write-only")

    async def join(self) -> None:
        raise EventChannelPermissionError("mailtruck channels are write-only")

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None


class ApixEventPipe:
    """Node-side event pipe with builtin, mailbox, and mailtruck channels."""

    def __init__(
        self,
        *,
        builtin: BaseEventChannel | None = None,
        mailbox: BaseEventChannel | None = None,
        mailtruck: BaseEventChannel | None = None,
        remote_enabled: bool = REMOTE_GATEWAY_ENABLE,
        mq_id: str = NODE_ID,
        node_name: str = NODE_NAME,
        channel_type: str = EVENT_CHANNEL_TYPE,
    ) -> None:
        self.remote_enabled = remote_enabled
        self.mq_id = mq_id
        self.node_name = node_name
        self.channel_type = channel_type
        self._event_pipe: dict[ChannelName, BaseEventChannel] = {
            "builtin": builtin or BuiltinChannel(maxsize=EVENT_PIPE_MAX_LEN),
            "mailbox": mailbox or self._build_mailbox(channel_type),
            "mailtruck": mailtruck or GatewayChannel(
                base_url=REMOTE_GATEWAY_BASE_URL,
                pipe_endpoint=REMOTE_GATEWAY_PIPE_ENDPOINT,
                node_id=mq_id,
                node_name=node_name,
                channel_type=channel_type,
                max_retry=GATEWAY_MAX_RETRY,
                retry_initial_delay=GATEWAY_RETRY_INITIAL_DELAY,
                timeout=GATEWAY_TIMEOUT,
            ),
        }
        self._mailbox_forwarder: asyncio.Task[None] | None = None
        self._nodes: dict[str, dict[str, Any]] = {}
        self._started = False

    def _build_mailbox(self, channel_type: str) -> BaseEventChannel:
        if not self.remote_enabled:
            return UnavailableMailboxChannel(
                "mailbox is unavailable while REMOTE_GATEWAY is disabled"
            )
        if channel_type == "kafka":
            return KafkaChannel(
                mq_id=self.mq_id,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                topic_prefix=KAFKA_TOPIC_PREFIX,
                group_id_prefix=KAFKA_GROUP_ID_PREFIX,
            )
        if channel_type == "rabbitmq":
            return RabbitMQChannel(
                mq_id=self.mq_id,
                url=RABBITMQ_URL,
                exchange=RABBITMQ_EXCHANGE,
                queue_prefix=RABBITMQ_QUEUE_PREFIX,
                prefetch_count=RABBITMQ_PREFETCH_COUNT,
            )
        raise ValueError(
            "EVENT_CHANNEL.type must be either 'kafka' or 'rabbitmq', "
            f"got {channel_type!r}."
        )

    @property
    def maxsize(self) -> int:
        return self._event_pipe["builtin"].maxsize

    @property
    def nodes(self) -> dict[str, dict[str, Any]]:
        return {node_id: dict(node) for node_id, node in self._nodes.items()}

    def get_channel(self, channel: ChannelName) -> BaseEventChannel:
        try:
            return self._event_pipe[channel]
        except KeyError as exc:
            raise ValueError(f"Unknown event channel: {channel!r}") from exc

    async def put(
        self,
        event: Any,
        channel: ChannelName = "builtin",
        *,
        recipient: str | None = None,
    ) -> None:
        if channel == "mailbox":
            raise EventChannelPermissionError("mailbox channels are receive-only")
        if channel == "mailtruck":
            await self.get_channel(channel).put(event, recipient=recipient)
            return
        await self.get_channel(channel).put(event)

    def put_nowait(
        self,
        event: Any,
        channel: ChannelName = "builtin",
    ) -> None:
        if channel == "mailbox":
            raise EventChannelPermissionError("mailbox channels are receive-only")
        self.get_channel(channel).put_nowait(event)

    async def get(self, channel: ChannelName = "builtin") -> Any:
        if channel == "mailtruck":
            raise EventChannelPermissionError("mailtruck channels are write-only")
        return await self.get_channel(channel).get()

    def get_nowait(self, channel: ChannelName = "builtin") -> Any:
        if channel == "mailtruck":
            raise EventChannelPermissionError("mailtruck channels are write-only")
        return self.get_channel(channel).get_nowait()

    def empty(self, channel: ChannelName = "builtin") -> bool:
        return self.get_channel(channel).empty()

    def full(self, channel: ChannelName = "builtin") -> bool:
        return self.get_channel(channel).full()

    def qsize(self, channel: ChannelName = "builtin") -> int:
        return self.get_channel(channel).qsize()

    def task_done(self, channel: ChannelName = "builtin") -> None:
        self.get_channel(channel).task_done()

    async def join(self, channel: ChannelName = "builtin") -> None:
        await self.get_channel(channel).join()

    async def send(self, event: ApixEvent, recipient: str) -> None:
        """Route an event to another node through the gateway."""
        await self.put(event, "mailtruck", recipient=recipient)

    async def broadcast(self, event: ApixEvent) -> dict[str, Any]:
        """Broadcast a node lifecycle event through the gateway."""
        if not self.remote_enabled:
            return {}
        mailtruck = self.get_channel("mailtruck")
        if not isinstance(mailtruck, GatewayChannel) and not hasattr(
            mailtruck, "broadcast"
        ):
            raise TypeError("mailtruck channel does not support broadcast()")
        result = await mailtruck.broadcast(event)  # type: ignore[attr-defined]
        self._update_nodes(result)
        return result

    def _update_nodes(self, payload: Any) -> None:
        if isinstance(payload, Mapping):
            payload = payload.get("nodes", payload)
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                if isinstance(value, Mapping):
                    node = dict(value)
                    node_id = str(node.get("node_id", key))
                    self._nodes[node_id] = node
        elif isinstance(payload, list):
            for value in payload:
                if isinstance(value, Mapping) and value.get("node_id"):
                    node = dict(value)
                    self._nodes[str(node["node_id"])] = node

    def _lifecycle_event(self, online: bool) -> ApixEvent:
        status = "ok" if online else "unavailable"
        return ApixEvent(
            event_id="event-" + uuid4().hex,
            event_type=EventType.LIFECYCLE,
            event_name="apix.node.online" if online else "apix.node.offline",
            context={
                "tag": self.node_name,
                "node_id": self.mq_id,
                "channel_config": EVENT_CHANNEL_CONFIG,
            },
            timestamp=time.time(),
            accepted=False,
        )

    async def _forward_mailbox(self) -> None:
        mailbox = self.get_channel("mailbox")
        builtin = self.get_channel("builtin")
        while True:
            event = await mailbox.get()
            try:
                await builtin.put(event)
            finally:
                mailbox.task_done()

    async def start(self) -> None:
        if self._started:
            return
        try:
            await self.get_channel("builtin").start()
            if self.remote_enabled:
                await self.get_channel("mailtruck").start()
                await self.get_channel("mailbox").start()
                self._mailbox_forwarder = asyncio.create_task(
                    self._forward_mailbox(),
                    name=f"mailbox-forwarder-{self.mq_id}",
                )
                await self.broadcast(self._lifecycle_event(online=True))
                mailtruck = self.get_channel("mailtruck")
                if hasattr(mailtruck, "fetch_nodes"):
                    self._update_nodes(
                        await mailtruck.fetch_nodes()  # type: ignore[attr-defined]
                    )
        except BaseException:
            await self._close_channels()
            raise
        self._started = True

    async def _close_channels(self) -> list[BaseException]:
        errors: list[BaseException] = []
        if self._mailbox_forwarder is not None:
            self._mailbox_forwarder.cancel()
            forwarder_result = await asyncio.gather(
                self._mailbox_forwarder,
                return_exceptions=True,
            )
            errors.extend(
                result
                for result in forwarder_result
                if isinstance(result, BaseException)
                and not isinstance(result, asyncio.CancelledError)
            )
            self._mailbox_forwarder = None

        results = await asyncio.gather(
            *(
                self.get_channel(channel_name).close()
                for channel_name in ("mailbox", "mailtruck", "builtin")
            ),
            return_exceptions=True,
        )
        errors.extend(
            result for result in results if isinstance(result, BaseException)
        )
        return errors

    async def stop(self) -> None:
        if not self._started:
            return
        errors: list[BaseException] = []
        if self.remote_enabled:
            try:
                await self.broadcast(self._lifecycle_event(online=False))
            except Exception as exc:
                errors.append(exc)

        errors.extend(await self._close_channels())
        self._started = False
        if errors:
            raise errors[0]


EVENT_PIPE = ApixEventPipe()
