# 事件系统

`apix.core.event` 提供进程级异步事件运行时。它负责：

- 创建和发布 `ApixEvent`。
- 按大小写敏感的 glob 模式匹配处理器。
- 以优先级或显式相邻关系确定处理器顺序。
- 在事件出队时确定候选 handler 名称和顺序，调用前读取当前对象并重新检查订阅和过滤条件。
- 使用本地队列分发事件，并可通过网关、Kafka 或 RabbitMQ 在节点之间转发。
- 记录运行期间已经观察到的精确事件名，支持插件诊断。

## 核心对象

| 对象 | 用途 |
| --- | --- |
| `ApixEvent` | 单个事件的数据模型 |
| `EventType` | 事件类别：`workflow`、`lifecycle`、`info`、`warning`、`error` |
| `EVENT_PIPE` | 默认全局事件管道 |
| `APIX_EVENT_LOOP` | 默认全局事件消费者与分发器 |
| `subscribe()` | 注册异步事件处理器 |
| `unsubscribe()` | 立即移除处理器和排序桶记录 |
| `APIX_HANDLER_REGISTRY` | 处理器、排序桶和单份当前链缓存 |
| `APIX_EVENT_REGISTRY` | 已观察到的精确事件名集合 |

类型别名：

- `EventHandlerFunc` 表示 `Callable[[ApixEvent], Awaitable[None]]`。
- `ChannelType` 表示 `Literal["builtin", "mailbox", "mailtruck"]`。

## 发布和处理一个事件

```python
import asyncio

from apix.core.event import (
    APIX_EVENT_LOOP,
    EVENT_PIPE,
    ApixEvent,
    EventType,
    unsubscribe,
    subscribe,
)


@subscribe("agent.message.created", priority=10, exist_ok=False)
async def log_created_message(event: ApixEvent) -> None:
    print(event.event_name, event.context)


async def main() -> None:
    try:
        await EVENT_PIPE.post_event(
            event_type=EventType.INFO,
            event_name="agent.message.created",
            context={"message_id": "msg-1"},
        )
        await EVENT_PIPE.join()
    finally:
        unsubscribe(log_created_message.__name__)
        await APIX_EVENT_LOOP.stop()


asyncio.run(main())
```

`post_event()` 负责生成 `event_id` 和时间戳。若调用方已经构造了 `ApixEvent`，可改用 `await EVENT_PIPE.put(event)`。

## ApixEvent

```python
@dataclass(slots=True)
class ApixEvent:
    event_id: str
    event_type: EventType
    event_name: str
    context: Any
    timestamp: float
    accepted: bool = False
    error_stack: list[ApixEventError] = field(default_factory=list)
```

公开成员：

| 成员 | 说明 |
| --- | --- |
| `event_id` | 事件唯一标识；`post_event()` 使用 `event-` 前缀生成 |
| `event_type` | `EventType` 枚举值 |
| `event_name` | 用于订阅匹配的精确名称，匹配时区分大小写 |
| `context` | 任意上下文；跨进程传输时必须可 JSON 序列化 |
| `timestamp` | Unix 时间戳 |
| `accepted` | 是否显式接受事件；后续 handler 跳过核心函数，仍执行通知 |
| `error_stack` | 按发生顺序保存前台 handler 的 `ApixEventError` 列表 |
| `has_error` | 只读属性，等价于 `bool(error_stack)` |
| `datetime` | 将 `timestamp` 转换为本地 `datetime` 的只读属性 |
| `accept()` | 将 `accepted` 设为 `True` |

事件不携带 handler_chain 版本。缓存与分发规则见[当前链缓存](./handlers.md#出队时解析当前链)。

## 接受事件与后续通知

前台处理器可以调用 `event.accept()`：

```python
@subscribe("request.*", priority=100)
async def reject_invalid_request(event: ApixEvent) -> None:
    if not event.context.get("authenticated"):
        event.context["error"] = "unauthorized"
        event.accept()
```

调用后，后续 handler 的 `core_func` 被跳过，但 `on_accepted` 仍会执行；如果已有错误，先调用 `on_has_error`。需要注意：

- 已经创建的后台处理器任务不会被撤销。
- 分发结束不会自动将事件标记为 accepted；该状态仅表示显式接受事件。
- 后台 handler 在实际开始执行时判断事件状态；尚未开始的任务也可能转入通知分支。
- `accept()` 控制的是当前事件实例，不会注销订阅。

## 事件循环

`ApixEventLoop` 从全局 `EVENT_PIPE` 的 `builtin` 通道消费事件。

如需隔离测试或构建独立运行时，可以创建 `ApixEventLoop(custom_registry)`；但当前实现仍从全局 `EVENT_PIPE` 消费，因此生产应用通常使用 `APIX_EVENT_LOOP`。

### 启动

```python
await APIX_EVENT_LOOP.start()
```

`start()` 可重复调用。全局 `EVENT_PIPE` 的本地发布（`post_event()`、`put()`、`put_nowait()`）会自动启动消费者，停止后再次发布也会重启。`put_nowait()` 需要在运行中的 asyncio loop 内调用。独立 `ApixEventPipe` 实例只负责自己的队列，不会启动全局消费者。

### 停止

```python
await APIX_EVENT_LOOP.stop()
```

`stop()` 只停止事件消费：不清空队列，不取消已经创建的分发任务或后台任务，已开始的调用继续完成。它不负责关闭外部通道，通道关闭仍使用 `EVENT_PIPE.stop()`。

如需等待本地队列中的事件完成分发，应在停止消费之前执行：

```python
await EVENT_PIPE.join()
```

分发任务的完成回调统一确认队列项并释放分发额度；正常完成、异常和取消（包括任务尚未开始时取消）均只清理一次。后台任务在创建前取得并发额度，并由完成回调释放；等待额度期间取消不会创建后台任务。

`join()` 只跟踪队列的 `put/get/task_done` 计数。后台处理器由分发器独立调度，因此队列完成不等于所有后台处理器都已结束。

## 分发错误策略

处理器异常和超时由 `ApixEventHandler.execute()` 统一处理，不会从 `EVENT_PIPE.post_event()` 反向抛给发布者，因为发布与处理是异步解耦的。

- `stop_when_error=True`：事件已有前置错误时，当前 handler 执行 `on_has_error`，跳过自己的 `core_func`。
- `stop_when_error=False`：执行错误通知后，事件未被 accepted 时继续运行自己的 `core_func`。
- `background=True`：核心函数和通知函数的未捕获异常、超时均只记录日志，不写入 `error_stack`，不影响其他 handler 的核心函数执行。
- `time_out=None`：无限等待；正数超时分别应用于每个实际调用的核心函数或通知函数。
- `time_out <= 0`：注册时被标准化为 `None`。

`on_has_error` 只负责处理前置 handler 的错误。当前 handler 的核心函数或通知函数抛出未捕获异常时，先记录错误，再调用 `on_error(event, exception)`，不会回调自己的 `on_has_error`。`on_error` 自身再抛错仅记录，不递归调用；正常返回不会消除原始错误或重试失败函数。后台 handler 也调用 `on_error`，但异常不写入事件错误栈。任务取消保持 `CancelledError` 传播，不调用 `on_error`，不作为业务错误记录。

需要局部恢复且不向事件记录错误时，仍在原函数内使用 `try/except/finally`。

每条 `ApixEventError` 包含 `handler_name`、`phase`、`exception_type`、`message`、`traceback`。`phase` 为 `core_func`、`on_has_error`、`on_accepted` 或 `on_error`；traceback 保存文本，不保留异常对象或活动栈帧。序列化会保留这些字段。

如果业务需要确认处理结果，应通过事件上下文中的 Future、队列或其他显式回传机制实现，而不是依赖 `post_event()` 返回值。

## 观察到的事件名

`APIX_EVENT_REGISTRY` 只记录成功发布过的精确事件名，不保存事件对象，也不负责分发：

```python
from apix.core.event import APIX_EVENT_REGISTRY

observed = APIX_EVENT_REGISTRY.get_registered_events()
print(observed)  # frozenset[str]
```

它的主要用途是诊断订阅是否覆盖了真实事件：

```python
from apix.core.event import get_unmatched_subscriptions

unmatched = get_unmatched_subscriptions("my_plugin_handler")
```

`clear()` 只清空观察记录，不会清空队列、处理器或处理器链缓存：

```python
APIX_EVENT_REGISTRY.clear()
```

`ApixEventRegistry` 本身是进程级 singleton；通常直接使用 `APIX_EVENT_REGISTRY`。如需依赖注入或类型标注，可以导入 class，但再次实例化仍会得到同一个 registry。

## 生命周期建议

应用启动时：

```python
await EVENT_PIPE.start()       # Required for remote channels
await APIX_EVENT_LOOP.start()
```

应用退出时：

```python
await EVENT_PIPE.join()
await APIX_EVENT_LOOP.stop()
await EVENT_PIPE.stop()
```

仅使用本地事件或 Graph Runtime 时，`EVENT_PIPE.start()` 不是必需的；但调用它也不会重复创建资源。

## 继续阅读

- [处理器注册、排序与当前链缓存](./handlers.md)
- [事件通道、序列化与远程传输](./channels.md)
- [Core Runtime 总览](../README.md)
