# 状态模型、Command 与复制语义

Graph Runtime 使用普通 `dict` 作为运行状态。`TypedDict` 或其他带类型注解的 class 只为运行时提供 `Annotated` 元数据，并不会阻止未声明 key 进入状态。

## 普通更新

没有 `AutoMerge` 时，节点返回的字段直接覆盖旧值：

```python
def update_status(state: dict) -> dict:
    return {"status": "ready"}
```

未出现在 update 中的字段保留。

## AutoMerge

使用 `Annotated[..., AutoMerge()]` 标记字段后，旧值存在时执行：

```python
new_value = current_value.__add__(update_value)
```

示例：

```python
from typing import Annotated, TypedDict

from apix.core.graph import AutoMerge


class State(TypedDict, total=False):
    messages: Annotated[list[str], AutoMerge()]
    score: Annotated[int, AutoMerge()]
```

节点返回：

```python
return {
    "messages": ["new message"],
    "score": 1,
}
```

若旧状态为 `{"messages": ["old"], "score": 2}`，提交后为：

```python
{"messages": ["old", "new message"], "score": 3}
```

规则：

- 字段尚不存在时直接用 update value 初始化，不调用 `__add__`。
- 运行时直接调用旧值的 `__add__`，不会尝试 `__radd__`。
- `__add__` 不可调用或返回 `NotImplemented` 时抛出 `TypeError`。
- `AutoMerge` 与 `AutoMerge()` 两种元数据形式都能识别。

自定义可变聚合器可以在 `__add__` 中返回自身：

```python
class MessageStore:
    def __init__(self) -> None:
        self.messages = []

    def __add__(self, incoming: list) -> "MessageStore":
        self.messages.extend(incoming)
        return self
```

如果该对象还使用 `KeepRef`，应仔细评估并发访问。

## Reset

`Reset(value)` 为一次更新显式绕过 `AutoMerge`：

```python
from apix.core.graph import Command, Reset


def clear_messages(state: State) -> Command:
    return Command(update={"messages": Reset([])})
```

运行时保存的是 `Reset.value`，wrapper 本身不会进入最终状态。

当字段尚不存在时，`Reset` 同样直接写入其 value。

## KeepRef

`KeepRef` 只控制运行时执行状态复制时的字段引用：

```python
from typing import Annotated, TypedDict

from apix.core.graph import KeepRef


class RuntimeState(TypedDict, total=False):
    resource: Annotated[object, KeepRef()]
    payload: dict
```

节点执行前：

- `resource` 与当前 `GraphContext.state["resource"]` 是同一个对象。
- `payload` 及其他普通字段被深拷贝。

因此节点可以直接修改共享资源，而无需通过 `Command.update` 回传：

```python
def use_resource(state: RuntimeState) -> dict:
    state["resource"].append("used")
    return {}
```

### KeepRef 的准确边界

`KeepRef` 不承诺整个调用生命周期始终使用同一个 state 字典，也不让所有后续处理都在原对象上执行。它只保证：

1. 节点执行前复制 state 时，该字段不被 deepcopy；
2. 应用 `Command` 复制旧 state 和显式 update 时，该字段继续保留引用。

外层 state mapping、普通字段和每次提交产生的 state mapping 仍可能是新对象。

### 快照例外

`GraphContext.take_a_snapshot()` 会对完整 recoverable state 使用 `copy.deepcopy()`，包括 `KeepRef` 字段。这样 abort 或 recovery 使用的是隔离快照，不会因为共享资源在节点中继续变动而污染历史状态。

`GraphContext.from_snapshot()` 也会再次深拷贝全部快照字段。

因此，被 `KeepRef` 标记的对象如果需要快照与恢复，仍必须支持 `deepcopy`。`KeepRef` 只能绕过节点状态复制，不能绕过快照复制。

### 并发风险

`KeepRef` 不推荐用于共享可变对象的并发场景。同一个引用可能被并发调用或异步任务同时修改，导致竞态、顺序不确定或回滚语义失真。

适合的对象包括调用内独占、无需复制的运行时资源；如果多个调用共享资源，应由资源本身提供锁、事务或其他并发控制。

`KeepRef` 与 `KeepRef()` 两种元数据形式都能识别。

## 同一字段组合多个 marker

一个字段可以同时使用 `AutoMerge` 和 `KeepRef`：

```python
class State(TypedDict):
    store: Annotated[
        MessageStore,
        AutoMerge(),
        KeepRef(),
    ]
```

其含义是：

- 节点状态复制时保留 `store` 引用；
- 节点用 update 更新 `store` 时调用旧对象的 `__add__`；
- 快照仍对 `store` 深拷贝。

## Command

```python
Command(
    update: dict[str, Any] = {},
    goto: str | None = omitted,
)
```

`goto` 有三种不同状态：

| 写法 | 路由行为 |
| --- | --- |
| `Command()` | 使用 manager 默认边；没有默认边时进入 `END` |
| `Command(goto=None)` | 显式进入 `END` |
| `Command(goto="next")` | 显式进入 `next` |

`Command.has_goto` 用于区分“省略 goto”和“显式传入 None”。

## 多 Command 提交

`ParallelNode` 和自定义 `BaseNode` 可以返回 `list[Command]`。运行时按顺序执行：

```python
return [
    Command(update={"history": ["first"]}),
    Command(update={"history": ["second"]}, goto="review"),
]
```

每个 command 的完整流程是：

1. 按 `KeepRef` 规则复制最新已提交 state。
2. 按 `KeepRef` 规则复制 update。
3. 逐字段应用 `Reset`、`AutoMerge` 或普通覆盖。
4. 将新 state 提交到 `GraphContext`。
5. 解析该 command 的 route。

后一条 command 看到前一条已经提交的 state。最后一条 command 的 route 成为节点最终 route；如果最后一条省略 `goto`，会重新使用 manager 默认边，而不是继承前一条 command 的显式 route。

空列表按一个空 `Command` 处理。

## 输入隔离

对不含 `KeepRef` 的 state：

- `invoke()` 和 `stream()` 绑定初始状态时深拷贝输入；
- 每个节点收到当前 state 的深拷贝；
- 每次 command 提交也基于复制后的 state；
- 最终状态与调用方的嵌套输入对象相互隔离。

示例：

```python
initial = {"items": []}


def mutate_only_local_copy(state: dict) -> dict:
    state["items"].append("inside")
    return {}


result = await graph.invoke(initial)

assert initial == {"items": []}
```

节点直接修改普通字段但不通过返回值提交时，该修改只发生在节点副本中，不会进入后续状态。这正是 `KeepRef` 与普通字段的核心差异。

## Schema 解析约束

运行时使用 `typing.get_type_hints(..., include_extras=True)` 解析 schema：

- `state_schema` 必须是 class 或 `None`。
- 未解析的 forward reference 会在 manager 创建/图编译或 context 创建时暴露。
- 普通 annotated class 和 `TypedDict` 都可以使用。
- schema 不负责验证节点 update 的 key 或 value 类型。
