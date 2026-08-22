# 事件通道、序列化与远程传输

`ApixEventPipe` 将事件通道分为三个固定角色：

| 通道 | 方向 | 默认实现 | 用途 |
| --- | --- | --- | --- |
| `builtin` | 读写 | `BuiltinChannel` | 当前进程内的事件分发队列 |
| `mailbox` | 只读 | `KafkaChannel` 或 `RabbitMQChannel` | 接收网关投递给当前节点的远程事件 |
| `mailtruck` | 只写 | `GatewayChannel` | 通过 HTTP 网关发送或广播事件 |

`APIX_EVENT_LOOP` 只消费 `builtin`。远程 mailbox 收到的事件由 `ApixEventPipe` 的 forwarder 转发到 `builtin`，所以处理器无需区分事件来源。

## ApixEventPipe API

全局实例：

```python
from apix.core.event import EVENT_PIPE
```

常用接口：

| 接口 | 说明 |
| --- | --- |
| `await post_event(...)` | 创建并发布一个事件 |
| `await put(event, channel=...)` | 发布已有事件 |
| `put_nowait(event)` | 无等待写入支持该操作的通道 |
| `await get(channel=...)` | 等待并取出事件 |
| `get_nowait(channel=...)` | 立即取出事件 |
| `empty()` / `full()` / `qsize()` | 查询通道本地缓冲区 |
| `task_done()` / `await join()` | asyncio.Queue 风格的完成跟踪 |
| `await clear()` | 移除并确认当前已经排队的事件 |
| `await send(event, recipient)` | 向指定远程节点发送事件 |
| `await broadcast(event)` | 广播节点级事件并更新节点目录 |
| `await start()` / `await stop()` | 打开或关闭外部通道与后台任务 |
| `nodes` | 返回远程节点目录的防御性副本 |
| `get_channel(name)` | 获取具体通道对象 |

## 本地事件

```python
await EVENT_PIPE.post_event(
    event_type=EventType.WORKFLOW,
    event_name="document.index.requested",
    context={"document_id": "doc-1"},
)
```

默认写入 `builtin`。在写入前会为事件冻结当前处理器链版本，并在成功写入后记录精确事件名。

如果队列已满，`put()` 会等待容量；`put_nowait()` 会抛出 `asyncio.QueueFull`。

## 直接操作队列

一般由 `APIX_EVENT_LOOP` 消费 `builtin`，应用不应同时竞争消费同一全局队列。自定义管道或测试中可以使用队列接口：

```python
event = await EVENT_PIPE.get()
try:
    ...
finally:
    EVENT_PIPE.task_done()

await EVENT_PIPE.join()
```

每次成功 `get()` 后都必须有一次 `task_done()`，否则 `join()` 不会完成。

## 事件序列化

远程传输使用以下 wire payload：

```python
{
    "event_id": "event-...",
    "event_type": "workflow",
    "event_name": "agent.task.created",
    "context": {"task_id": "task-1"},
    "timestamp": 1787414400.0,
    "accepted": False,
}
```

内部辅助函数位于 `apix.core.event.event_pipe`：

```python
from apix.core.event.event_pipe import (
    encode_event,
    event_from_payload,
    event_to_payload,
)
```

- `event_to_payload(event)` 将 `ApixEvent` 转为字典。
- `encode_event(event)` 生成 UTF-8 JSON bytes，用于 Kafka 或 RabbitMQ。
- `event_from_payload(payload)` 接受 mapping、JSON string、bytes，或直接返回传入的 `ApixEvent`。
- `event_from_payload()` 也能解析 `{"event": {...}}` 形式的网关路由 envelope。

跨进程传输时，`context` 必须可 JSON 序列化。编码器额外支持 `Enum` 和 dataclass 实例；其他复杂运行时对象（例如 `GraphContext`、Future、文件句柄）只适合本地 `builtin` 通道。

## 远程发送

### 点对点发送

```python
event = ApixEvent(
    event_id="event-task-1",
    event_type=EventType.WORKFLOW,
    event_name="worker.execute",
    context={"task_id": "task-1"},
    timestamp=time.time(),
)

await EVENT_PIPE.send(event, recipient="worker-node-id")
```

`recipient` 必须是非空 mq id。`GatewayChannel` 通过 HTTP POST 请求网关的 pipe endpoint，并携带 sender、recipient 和事件 payload。

`mailtruck` 是异步 HTTP 写通道，不支持 `put_nowait()`、`get()` 或队列状态查询；误用时抛出 `EventChannelPermissionError`。

### 广播

```python
result = await EVENT_PIPE.broadcast(event)
nodes = EVENT_PIPE.nodes
```

当远程网关未启用时，`broadcast()` 直接返回空字典。

### 重试

网关请求对以下情况重试：

- `httpx.RequestError`；
- HTTP 503。

退避时间为 `retry_initial_delay * 2**retry`。其他非成功状态直接通过 `raise_for_status()` 抛出。

## mailbox

`mailbox` 是接收专用于当前节点的外部事件的只读通道：

- `KafkaChannel` 消费 `${topic_prefix}.${mq_id}`，group id 为 `${group_id_prefix}.${mq_id}`。
- `RabbitMQChannel` 声明 direct exchange，并用当前 `mq_id` 作为 routing key 绑定 `${queue_prefix}.${mq_id}` 队列。
- broker 消息被反序列化为 `ApixEvent`，进入本地缓冲区。
- forwarder 将其转发到 `builtin`，同时冻结本节点当前处理器链版本。

直接向 mailbox 调用 `put()` 或 `put_nowait()` 会抛出 `EventChannelPermissionError`。

## 配置

`source/config.yaml` 中的相关配置如下：

```yaml
REMOTE_GATEWAY:
  enable: true
  base_url: "http://localhost:8080"
  config_endpoint: "/api/config"
  pipe_endpoint: "/api/pipe"
  max_retry: 5
  retry_initial_delay: 1.0
  timeout: 10.0

SERVER:
  node_name: "apix_service"

PIPELINE:
  event_pipe_max_len: 1024

EVENT_CHANNEL:
  type: "kafka"  # kafka | rabbitmq

  kafka:
    bootstrap_servers:
      - "localhost:9092"
    topic_prefix: "apix.mailbox"
    group_id_prefix: "apix.node"

  rabbitmq:
    url: "amqp://guest:guest@localhost/"
    exchange: "apix.events"
    queue_prefix: "apix.mailbox"
    prefetch_count: 100
```

启用远程模式时还有两个跨节点约束：

- `DATA_STORE.type=sqlite` 不可用，应选择分布式数据存储。
- `CACHE.store_type=builtin` 不可用，应选择共享缓存后端。

`EVENT_CHANNEL` 是节点本地配置，不会从远程配置中心继承，避免多个节点错误消费同一个 mailbox 身份。

## 自定义通道

可以为独立 `ApixEventPipe` 注入实现了 `BaseEventChannel` 的对象：

```python
pipe = ApixEventPipe(
    builtin=CustomBuiltinChannel(),
    mailbox=CustomMailboxChannel(),
    mailtruck=CustomGatewayChannel(),
    remote_enabled=True,
    mq_id="node-1",
    node_name="worker",
    channel_type="kafka",
)
```

自定义通道需要实现以下 queue-like 接口：

```python
class BaseEventChannel(ABC):
    @property
    def maxsize(self) -> int: ...

    async def start(self) -> None: ...
    async def put(self, event: Any, **kwargs: Any) -> None: ...
    def put_nowait(self, event: Any) -> None: ...
    async def get(self) -> Any: ...
    def get_nowait(self) -> Any: ...
    def empty(self) -> bool: ...
    def full(self) -> bool: ...
    def qsize(self) -> int: ...
    def task_done(self) -> None: ...
    async def join(self) -> None: ...
    async def close(self) -> None: ...
```

`ApixEventPipe` 的角色约束仍然有效：mailbox 由 pipe 读取，mailtruck 由 pipe 写入。若自定义 mailtruck 支持广播和节点发现，还应提供异步 `broadcast(event)` 与 `fetch_nodes()`。

## 生命周期与失败处理

```python
await EVENT_PIPE.start()
try:
    await APIX_EVENT_LOOP.start()
    ...
finally:
    await APIX_EVENT_LOOP.stop()
    await EVENT_PIPE.stop()
```

`EVENT_PIPE.start()` 是幂等的。如果启动任一外部通道失败，已打开的通道会被关闭。

`EVENT_PIPE.stop()` 会：

1. 尝试广播 offline 生命周期事件；
2. 取消 mailbox forwarder；
3. 按 mailbox、mailtruck、builtin 顺序并发关闭通道；
4. 若存在错误，清理后重新抛出第一个错误。

缺少可选 broker 依赖时：

- Kafka 抛出 `EventChannelUnavailableError`，提示安装 `aiokafka`。
- RabbitMQ 抛出 `EventChannelUnavailableError`，提示安装 `aio-pika`。

