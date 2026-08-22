# 事件系统

`apix.core.event` 提供进程级异步事件运行时。它负责：

- 创建和发布 `ApixEvent`。
- 按大小写敏感的 glob 模式匹配处理器。
- 以优先级或显式相邻关系确定处理器顺序。
- 在事件入队时冻结处理器链版本，隔离后续动态注册或注销。
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
| `unsubscribe()` | 停用处理器的全部或部分订阅 |
| `delete_handler_from_registry()` | 永久删除处理器元数据 |
| `APIX_HANDLER_REGISTRY` | 处理器、排序桶和版本化链缓存 |
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
    delete_handler_from_registry,
    subscribe,
)


@subscribe("agent.message.created", priority=10, exist_ok=False)
async def log_created_message(event: ApixEvent) -> None:
    print(event.event_name, event.context)


async def main() -> None:
    await APIX_EVENT_LOOP.start()
    try:
        await EVENT_PIPE.post_event(
            event_type=EventType.INFO,
            event_name="agent.message.created",
            context={"message_id": "msg-1"},
        )
        await EVENT_PIPE.join()
    finally:
        delete_handler_from_registry(log_created_message.__name__)
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
```

公开成员：

| 成员 | 说明 |
| --- | --- |
| `event_id` | 事件唯一标识；`post_event()` 使用 `event-` 前缀生成 |
| `event_type` | `EventType` 枚举值 |
| `event_name` | 用于订阅匹配的精确名称，匹配时区分大小写 |
| `context` | 任意上下文；跨进程传输时必须可 JSON 序列化 |
| `timestamp` | Unix 时间戳 |
| `accepted` | 是否已停止后续前台处理器分发 |
| `datetime` | 将 `timestamp` 转换为本地 `datetime` 的只读属性 |
| `accept()` | 将 `accepted` 设为 `True` |

`_handler_chain_version` 是运行时内部字段，用于保存事件入队时的处理器链版本。应用代码不应手动修改。

## 停止后续处理器

前台处理器可以调用 `event.accept()`：

```python
@subscribe("request.*", priority=100)
async def reject_invalid_request(event: ApixEvent) -> None:
    if not event.context.get("authenticated"):
        event.context["error"] = "unauthorized"
        event.accept()
```

调用后，当前事件尚未执行的前台处理器会被跳过。需要注意：

- 已经创建的后台处理器任务不会被撤销。
- 分发器在正常完成处理器链后也会将事件标记为 accepted。
- `accept()` 控制的是当前事件实例，不会注销订阅。

## 事件循环

`ApixEventLoop` 从全局 `EVENT_PIPE` 的 `builtin` 通道消费事件。

如需隔离测试或构建独立运行时，可以创建 `ApixEventLoop(custom_registry)`；但当前实现仍从全局 `EVENT_PIPE` 消费，因此生产应用通常使用 `APIX_EVENT_LOOP`。

### 启动

```python
await APIX_EVENT_LOOP.start()
```

`start()` 可重复调用。`NodeGraph.invoke()` 和 `NodeGraph.stream()` 会自动启动它。

### 停止

```python
await APIX_EVENT_LOOP.stop()
```

停止时会取消：

- 事件消费者任务；
- 尚未结束的事件分发任务；
- 尚未结束的后台处理器任务。

如果只希望等待当前本地队列中已经取出的事件处理完成，应先执行：

```python
await EVENT_PIPE.join()
```

`join()` 只跟踪队列的 `put/get/task_done` 计数。后台处理器由分发器独立调度，因此队列完成不等于所有后台处理器都已结束。

## 分发错误策略

处理器异常和超时由事件循环记录，不会从 `EVENT_PIPE.post_event()` 反向抛给发布者，因为发布与处理是异步解耦的。

- `stop_when_error=True`：当前前台处理器失败后停止该事件的后续处理器。
- `stop_when_error=False`：记录错误后继续分发。
- `background=True`：异常只记录日志，不影响前台链。
- `time_out=None`：无限等待。
- `time_out <= 0`：注册时被标准化为 `None`。

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

- [处理器注册、排序与版本隔离](./handlers.md)
- [事件通道、序列化与远程传输](./channels.md)
- [Core Runtime 总览](../README.md)
