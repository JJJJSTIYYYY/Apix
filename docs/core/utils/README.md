# Core 异常类型

`apix.core.utils.exception` 定义事件系统和 Graph Runtime 的公共异常。事件模块会重新导出这些类型，通常可以直接从 `apix.core.event` 导入。

## 事件异常

### EventHandlerNotRegisteredError

处理器名称不存在，或 `between_handlers` 引用的边界处理器已经不再 active 时抛出。

常见来源：

- `unsubscribe(..., missing_ok=False)`；
- `delete_handler_from_registry(..., missing_ok=False)`；
- `get_unmatched_subscriptions()` 使用未知名称；
- 注册时指定不存在的 `between_handlers` 边界。

### EventHandlerAlreadyRegisteredError

处理器函数名已经存在且 `exist_ok=False` 时抛出。处理器名称在进程全局 registry 中唯一。

### EventChannelError

事件通道错误的 RuntimeError 基类。

### EventChannelPermissionError

同时继承 `PermissionError` 和 `EventChannelError`，表示通道方向不支持当前操作，例如：

- 向只读 mailbox 写入；
- 从只写 mailtruck 读取；
- 对 mailtruck 使用 `put_nowait()`。

### EventChannelUnavailableError

配置的通道当前不可用，例如远程网关未启用却读取 mailbox，或缺少 Kafka/RabbitMQ 客户端依赖。

## 图异常

### InvalidNodeReturnsError

普通节点返回了运行时无法转换成 `Command` 的值，例如 `None`、整数或 `list[Command]`；也可能是 `Command.update` 不是 mapping，或 `goto` 类型非法。

### GraphNodeError

图节点错误的通用异常类型。目前常规 `NodeGraph` 执行会直接传播节点原始异常、`InvalidNodeReturnsError`、`TimeoutError`、`ValueError` 等，并不会统一包装为 `GraphNodeError`。自定义扩展可以在需要统一错误分类时使用此类型。

## 导入示例

```python
from apix.core.event import (
    EventChannelError,
    EventChannelPermissionError,
    EventChannelUnavailableError,
    EventHandlerAlreadyRegisteredError,
    EventHandlerNotRegisteredError,
    InvalidNodeReturnsError,
)
```

或从定义模块导入：

```python
from apix.core.utils.exception import GraphNodeError
```

## 错误处理边界

事件处理器异常由 `APIX_EVENT_LOOP` 捕获并记录，通常不会传播回事件发布者。Graph 节点异常则通过 `GraphContext.completion` 传播给 `NodeGraph.invoke()` 或 `NodeGraph.stream()` 的调用方。

```python
try:
    result = await graph.invoke(state)
except InvalidNodeReturnsError:
    ...
except TimeoutError:
    ...
```

对于事件订阅生命周期错误，应在插件安装/卸载阶段显式检查，而不是依赖分发日志：

```python
try:
    delete_handler_from_registry(
        "required_handler",
        missing_ok=False,
    )
except EventHandlerNotRegisteredError:
    ...
```

