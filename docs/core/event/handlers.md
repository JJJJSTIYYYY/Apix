# 处理器注册、排序与版本隔离

本页详细说明 `apix.core.event.handler_registry` 的用户级行为。

## subscribe()

```python
subscribe(
    *event_names: str,
    exist_ok: bool = True,
    priority: float | None = None,
    between_handlers: tuple[str | None, str | None] | None = None,
    filter_event: list[str] | None = None,
    stop_when_error: bool = True,
    time_out: float | None = None,
    background: bool = False,
)
```

装饰器只接受异步处理器作为正常用法。处理器收到一个 `ApixEvent`，并返回 `None`。

```python
from apix.core.event import ApixEvent, subscribe


@subscribe("agent.*", priority=10)
async def observe_agent_event(event: ApixEvent) -> None:
    print(event.event_name)
```

### 参数

| 参数 | 行为 |
| --- | --- |
| `event_names` | 一个或多个精确名称或 glob 模式；不能为空 |
| `exist_ok` | 同名函数已存在时是否忽略本次注册；去重依据仅为函数名 |
| `priority` | 数值越大越先执行；同优先级保持注册顺序；默认 `1` |
| `between_handlers` | 按已注册函数名将新处理器插入指定边界；不能与 `priority` 同用 |
| `filter_event` | 在订阅命中后继续排除的 glob 模式 |
| `stop_when_error` | 前台处理器异常后是否停止后续前台链 |
| `time_out` | 最大运行秒数；`None` 或非正数表示无限等待 |
| `background` | 是否创建后台任务并立即继续分发 |

## 匹配语义

订阅和过滤均使用 `fnmatch.fnmatchcase`，因此：

- 匹配大小写敏感。
- `*` 匹配任意数量字符。
- `?` 匹配一个字符。
- `[abc]` 匹配集合内的一个字符。
- `[a-z]` 匹配字符范围。
- `[!abc]` 匹配不在集合中的一个字符。
- 点号 `.`、斜杠 `/` 没有特殊的路径分隔语义，`*` 可以跨越它们。

```python
@subscribe(
    "graph.*",
    filter_event=["graph.internal.*", "graph.debug.??"],
)
async def observe_public_graph_events(event: ApixEvent) -> None:
    ...
```

该处理器会接收 `graph.started`，不会接收 `Graph.started` 或 `graph.internal.snapshot`。

重复模式会按首次出现顺序去重。

## 优先级排序

默认排序规则为：

1. 优先级较大的处理器先执行。
2. 相同优先级内按注册顺序执行。

```python
@subscribe("order.created", priority=20)
async def validate_order(event: ApixEvent) -> None:
    ...


@subscribe("order.created", priority=10)
async def persist_order(event: ApixEvent) -> None:
    ...
```

`validate_order` 会先于 `persist_order` 执行。

`priority` 必须是有限数值，不能是 `bool`、`NaN` 或无穷大。

## 显式插入位置

当插件需要相对于已有处理器插入，而不是猜测对方的优先级时，可使用 `between_handlers`。

### 插入到右侧处理器之前

```python
@subscribe(
    "order.*",
    between_handlers=(None, "persist_order"),
)
async def enrich_order(event: ApixEvent) -> None:
    ...
```

### 插入到左侧处理器之后

```python
@subscribe(
    "order.*",
    between_handlers=("validate_order", None),
)
async def audit_validated_order(event: ApixEvent) -> None:
    ...
```

### 插入到两个边界之间

```python
@subscribe(
    "order.*",
    between_handlers=("validate_order", "persist_order"),
)
async def normalize_order(event: ApixEvent) -> None:
    ...
```

两个边界都存在时，新处理器紧邻右边界之前插入；原本位于左右边界之间的处理器仍在新处理器之前。

约束：

- 边界使用处理器函数名，不是事件名或 handler id。
- 边界处理器必须仍处于 active 状态。
- `(None, None)` 无效。
- 左右边界不能相同。
- 左边界必须本来就排在右边界之前。
- `between_handlers` 与显式 `priority` 不能同时提供。

## 发布时版本隔离

处理器链并不是消费事件时才首次决定。事件进入本地 `builtin` 队列时，`ApixEventPipe` 会：

1. 为该精确事件名解析当前处理器链；
2. 将链的版本号写入事件；
3. 再把事件放入队列。

因此，事件发布之后发生的注册、部分注销或全部注销，不会改变该事件已经冻结的处理器顺序。

```python
await EVENT_PIPE.post_event(
    event_type=EventType.INFO,
    event_name="task.ready",
)

# This handler only affects events published after registration.
@subscribe("task.ready", priority=100)
async def late_handler(event: ApixEvent) -> None:
    ...
```

处理器链按精确事件名懒解析和缓存。注册一个宽泛通配符不会预热所有已观察事件，也不会为未知事件枚举名称。

## 后台处理器

```python
@subscribe(
    "audit.*",
    background=True,
    time_out=5,
)
async def write_audit_log(event: ApixEvent) -> None:
    ...
```

后台处理器的行为：

- 分发器创建任务后立即继续处理下一个 handler。
- 后台任务之间最多并发 100 个。
- 异常和超时只记录日志。
- `stop_when_error` 对后台异常没有停止前台链的作用。
- 后续前台处理器调用 `event.accept()` 时，已经开始的后台任务不会被取消。

如果处理器必须在下一个处理器之前完成，不要设置 `background=True`。

## 注销与删除

### 部分注销

```python
unsubscribe(
    "observe_agent_event",
    ["agent.internal.*"],
)
```

部分注销会把模式加入处理器的 `filter_event`，处理器仍然 active，并继续接收其他订阅事件。

### 全部注销

```python
unsubscribe("observe_agent_event")
```

全部注销会把处理器从 active 排序桶移除，但保留 registry entry。保留 entry 是为了让已经发布、绑定了旧链版本的事件仍能解析到原处理器。

### 永久删除

```python
delete_handler_from_registry("observe_agent_event")
```

永久删除会移除处理器 entry 和 active 排序引用。它适合插件卸载或图 `decompose()` 后的最终清理。

注意：如果仍有绑定旧版本的事件在队列中，永久删除可能导致旧链中的处理器名无法解析；分发器会记录警告并跳过该处理器。因此，在可能存在排队事件时优先使用 `unsubscribe()`，待生命周期结束后再永久删除。

两个函数都默认 `missing_ok=True`。需要严格检查时：

```python
unsubscribe("required_handler", missing_ok=False)
delete_handler_from_registry("required_handler", missing_ok=False)
```

## 注册诊断

### 读取元数据

```python
meta = get_handler_meta("observe_agent_event")
```

返回字段包括：

```python
{
    "id": "handler-...",
    "name": "observe_agent_event",
    "register_order": 0,
    "subscribe": ["agent.*"],
    "filter_event": [],
    "priority": 10,
    "between_handlers": None,
    "stop_when_error": True,
    "time_out": None,
    "background": False,
}
```

调用前应确认处理器存在；当前实现面向已注册名称使用。

### 找出尚未匹配的订阅

```python
patterns = get_unmatched_subscriptions("observe_agent_event")
```

该结果基于 `APIX_EVENT_REGISTRY` 已观察到的精确事件名。应用刚启动、尚未发布事件时，所有订阅模式都可能被报告为 unmatched。

## 低级数据模型与 Registry API

大多数应用应使用模块级 `subscribe()`、`unsubscribe()` 和 `delete_handler_from_registry()`。框架扩展或诊断工具也可以直接使用 `ApixEventHandler` 与 `ApixHandlerRegistry`。

### ApixEventHandler

```python
from apix.core.event import ApixEventHandler
```

该 dataclass 保存一个处理器 entry：

| 字段 | 说明 |
| --- | --- |
| `name` | 全局唯一处理器名 |
| `register_order` | 注册顺序编号 |
| `callback` | 异步 event callback |
| `id` | 自动生成的 `handler-...` 标识 |
| `subscribe` | 包含模式列表 |
| `filter_event` | 排除模式列表 |
| `priority` | 优先级；边界插入时为 `None` |
| `between_handlers` | 注册时指定的相对位置 |
| `stop_when_error` | 前台错误停止策略 |
| `time_out` | handler timeout |
| `background` | 是否后台执行 |

直接构造后可使用 `APIX_HANDLER_REGISTRY.register_handler(entry)` 注册。Registry 会再次验证模式、callback、priority 和边界，并更新受影响的精确事件链版本。

### ApixHandlerRegistry

该类是进程级 singleton；新建 `ApixHandlerRegistry()` 得到的仍是全局同一实例。主要方法：

| 方法 | 说明 |
| --- | --- |
| `register_handler(entry)` | 注册一个完整 `ApixEventHandler` |
| `unregister_handler(name, event_names=None)` | 部分或全部停用，保留旧版本 entry |
| `delete_handler_from_registry(name, event_names=None)` | 永久删除 entry |
| `get_handler(name)` | 返回 entry 或 `None` |
| `get_handlers_chain_for_event(event_name, version=None)` | 获取精确事件某版本的处理器名顺序 |
| `get_current_version_for_event(event_name)` | 解析当前链并返回版本号 |
| `get_current_version_for_event_without_resolve(event_name)` | 仅查询已有缓存版本；未出现时返回 `None` |
| `get_unmatched_subscriptions(name)` | 返回未覆盖已观察事件的订阅模式 |

`registry`、`priority_buckets` 和 `cached_chain` 是可见的运行时结构，但应用不应直接修改，否则无法同步完成版本失效与旧事件隔离。

历史链 version 必须是从 0 开始的有效非负整数。与 GraphContext snapshot version 不同，handler chain API 不接受负索引。

## 插件清理模板

```python
from apix.core.event import (
    ApixEvent,
    delete_handler_from_registry,
    subscribe,
    unsubscribe,
)


class Plugin:
    def install(self) -> None:
        @subscribe("agent.*", exist_ok=False)
        async def plugin_agent_observer(event: ApixEvent) -> None:
            ...

        self.handler_name = plugin_agent_observer.__name__

    def disable(self) -> None:
        unsubscribe(self.handler_name)

    def uninstall(self) -> None:
        delete_handler_from_registry(self.handler_name)
```

处理器名在进程全局唯一。多个插件若可能定义同名函数，应给函数设置稳定且带插件前缀的 `__name__`，并使用 `exist_ok=False` 及时暴露冲突。
