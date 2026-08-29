# Graph Runtime

`apix.core.graph` 用事件系统驱动有向状态图。用户通过 `GraphManager` 声明节点和转移，编译得到 `NodeGraph`，再使用 `invoke()` 或 `stream()` 执行。

## 核心类型

| 类型 | 用途 |
| --- | --- |
| `GraphManager` | 构建节点、边、条件与路由 |
| `NodeGraph` | 编译后的可执行图 |
| `Node` | 将普通同步或异步函数包装为节点 |
| `ParallelNode` | 并发执行多个分支，并按声明顺序汇聚命令 |
| `BaseNode` | 自定义节点基类，允许返回多个 `Command` |
| `Command` | 提交状态更新并可覆盖下一节点 |
| `AutoMerge` | 标记字段使用 `__add__` 合并更新 |
| `Reset` | 为单次更新绕过 `AutoMerge`，直接替换字段 |
| `KeepRef` | 节点执行前复制状态时保留字段引用 |
| `GraphContext` | 一次调用尝试的状态、生命周期和快照 |
| `START` / `END` | 图的预定义入口与出口 |

公开类型别名中，`NodeResult` 表示普通节点可返回的 `dict | Command`，`NodeFunction` 表示接收 state 并同步或异步返回 `NodeResult` 的 callable。专用 `BaseNode.execute()` 还可以返回 `list[Command]`。

## 构建线性图

```python
from typing import TypedDict

from apix.core.graph import END, GraphManager, START


class State(TypedDict, total=False):
    value: int
    result: int


def double(state: State) -> dict:
    return {"result": state["value"] * 2}


graph = (
    GraphManager(State)
    .add_node(double)
    .add_edge(START, "double")
    .add_edge("double", END)
    .compile_graph(using_namespace="double-flow")
)

result = await graph.invoke({"value": 21})
assert result == {"value": 21, "result": 42}
```

从 `START` 出发的转移是必需的。普通节点若没有显式出边，会默认进入 `END`，因此上例最后一条 `add_edge()` 可以省略。

## GraphManager

### 创建 manager

```python
manager = GraphManager(state_schema=State)
```

`state_schema` 可选。它不对字典执行运行时字段校验，而是用于解析 `Annotated` 中的 `AutoMerge` 和 `KeepRef` 元数据。

### 添加节点

```python
manager.add_node(node_func, node_name=None, timeout=None)
manager.add_nodes([first, second, third])
```

- `node_func` 可以是同步函数、异步函数或 `BaseNode` 实例。
- 普通函数的默认节点名为 `func.__name__`。
- `START` 和 `END` 是保留名称。
- 同一 manager 中节点名必须唯一。
- `timeout=None` 或非正数表示不限制；正数必须有限。
- 传入 `BaseNode` 时使用该对象自身的 `name`。

```python
async def fetch(state: State) -> dict:
    ...


manager.add_node(fetch, timeout=10)
manager.add_node(lambda state: {"ready": True}, "prepare")
```

### 添加直接边

```python
manager.add_edge("prepare", "fetch")
```

每个 source 只能由 manager 定义一条默认出边。需要多路选择时使用条件边、router，或让节点返回带 `goto` 的 `Command`。

### 添加条件边

```python
def has_work(state: State) -> bool:
    return bool(state.get("items"))


manager.add_edge("prepare", "process", condition=has_work)
```

运行时会在 `prepare` 后插入一个内部条件节点：

- 返回 `True`：进入 `process`。
- 返回 `False`：直接进入 `END`。
- 返回非 `bool`：调用失败并向 `invoke()` 或 `stream()` 传播 `TypeError`。
- 条件函数可以是同步或异步函数。

条件节点只是路由，不提交业务状态更新。

### 添加 router

```python
def select_route(state: State) -> str:
    return "fast" if state["priority"] > 5 else "normal"


manager.add_router(
    "prepare",
    ["fast", "normal", END],
    select_route,
)
```

router 可以返回：

- 声明在 `r_nodes` 中的字符串；
- `Command(goto="...")`；
- `{"goto": "..."}`。

返回目标必须已经列入 `r_nodes`。没有显式 `goto` 的 `Command`、不含 `goto` 的 mapping，或未知目标都会导致 `ValueError`。

router 自身生成一个内部节点。内部条件和 router 节点也会占用一次执行 step。

## 节点返回值

普通函数节点必须返回以下之一：

```python
{"key": "value"}

Command(update={"key": "value"})

Command(update={"key": "value"}, goto="next_node")

Command(goto=None)  # Explicitly route to END
```

空字典是有效更新。普通 `Node` 不接受 `None` 或 `list[Command]`。

一个容易混淆的规则是：普通节点返回的 mapping 永远被当作状态更新，即使它含有名为 `goto` 的 key：

```python
def node(state: dict) -> dict:
    return {"goto": "this_is_state_data"}
```

只有真正的 `Command` 可以从普通节点选择下一节点。mapping 形式的 `{"goto": ...}` 仅由 `add_router()` 的 router 函数特殊识别。

### 默认路由与显式路由

- 未向 `Command` 传入 `goto`：使用 manager 为当前节点定义的默认出边；若没有则进入 `END`。
- `goto=None`：显式进入 `END`。
- `goto="node"`：覆盖默认边。
- 未知节点名：运行失败并传播 `ValueError`。

## 并行分支与确定性汇聚

`ParallelNode` 将多个普通节点函数作为同一个图节点的并行分支：

```python
from typing import Annotated, Any, TypedDict

from apix.core.graph import (
    AutoMerge,
    GraphManager,
    ParallelNode,
    START,
)


class AgentState(TypedDict):
    user_id: str
    context: Annotated[list[Any], AutoMerge()]


async def load_profile(state: AgentState) -> dict:
    profile = await fetch_profile(state["user_id"])
    return {"context": [profile]}


async def load_memory(state: AgentState) -> dict:
    memory = await fetch_memory(state["user_id"])
    return {"context": [memory]}


prepare_context = ParallelNode(
    [load_profile, load_memory],
    name="prepare_context",
)

graph = (
    GraphManager(AgentState)
    .add_node(prepare_context)
    .add_edge(START, prepare_context.name)
    .compile_graph()
)
```

执行与汇聚语义：

1. 所有分支被创建为独立 asyncio task，并发执行。
2. 每个分支必须返回一个 mapping 或 `Command`，不能返回嵌套的 `list[Command]`。
3. 所有分支完成后，结果始终按分支声明顺序组成 `list[Command]`，与完成先后无关。
4. `NodeGraph` 按该顺序逐个提交 command，因此 `AutoMerge` 的累积顺序和普通字段的覆盖结果是确定的。
5. 多个分支都指定 `goto` 时，声明顺序靠后的分支决定最终 route；未指定时使用节点默认边。
6. 任一分支失败，尚未完成的兄弟任务会被取消并等待回收，然后原始异常传播给图调用方。
7. 节点 timeout 或外部任务取消同样会清理所有未完成分支。

所有分支接收同一份节点级 state 快照，而不是各自的 deepcopy。分支应把 state 当作只读输入，并通过返回值提交更新。直接并发修改普通嵌套对象会造成分支间干扰；并发修改 `KeepRef` 对象还可能影响调用方持有的共享资源，因此必须由资源自身提供并发控制。

`ParallelNode` 表达的是“一个图节点内部的 fan-out/fan-in”：分支具有并发执行和统一汇聚，但没有各自独立的图边、快照或中断入口。如果每个分支都需要独立路由和生命周期，则仍需要更高层的图拓扑能力。

## 自定义 BaseNode

普通 `Node` 一次只返回一个 `Command`。除通用的 `ParallelNode` 外，工具节点等需要自行生成多份命令的组件也可以继承 `BaseNode`：

```python
from apix.core.graph import BaseNode, Command


class BatchNode(BaseNode):
    def __init__(self, name: str = "batch") -> None:
        self.name = name

    async def execute(self, state: dict) -> list[Command]:
        return [
            Command(update={"first": True}),
            Command(update={"second": True}, goto="done"),
        ]
```

命令按原顺序逐个提交；后一条命令看到前一条已经提交的状态，最后一条命令决定最终路由。空列表等价于一个空 `Command`。

## 编译与命名空间

```python
graph = manager.compile_graph(
    using_namespace="agent-runtime",
    exist_ok=False,
)
```

命名空间用于隔离编译图拥有的事件处理器及运行上下文：

- `None` 或空字符串选择全局命名空间。
- `<global>` 是保留文本，不能作为命名空间。
- 同一时刻一个命名空间只能由一个已编译图占用。
- `exist_ok=False` 时发生冲突会抛出 `ValueError`。
- `exist_ok=True` 会先分解旧图，再创建替代图。
- 旧图有活跃调用时无法替换，会抛出 `RuntimeError`。

节点事件会使用 `using_namespace` 限定作用域。全局 namespace 保持原节点名；非全局 namespace 的事件名由 `get_node_name_in_namespace()` 生成。不同 namespace 中的同名节点具有不同事件处理链，不会再调度其他图的节点监听器。`GraphContext` 的 namespace 检查仍作为运行时防御。

模块导出的 `namespace_set` 可用于只读诊断当前被占用的 namespace。不要直接增删其中的值；正常释放必须经过 `graph.decompose()`，以同时清理图索引和事件处理器。

## invoke()

```python
result = await graph.invoke(initial_state, graph_context=None)
```

行为：

- `initial_state` 必须是 `dict`。
- 初始状态在绑定上下文时复制，普通嵌套值不会修改调用方输入。
- 返回最终已提交状态的副本。
- 节点异常、超时、非法返回或非法路由会由 await 抛给调用方。
- 可选 `graph_context` 用于外部 abort 和后续快照恢复。

同一个 `NodeGraph` 可以并发 `invoke()`；每次调用使用独立 `GraphContext` 和完成 Future。

## stream()

```python
async for chunk in graph.stream(initial_state, graph_context=None):
    print(chunk)
```

节点使用 `get_stream_writer()` 发出自定义对象：

```python
from apix.core.graph.context import get_stream_writer


async def generate(state: dict) -> dict:
    writer = get_stream_writer()
    writer({"type": "start"})
    writer.write({"type": "token", "text": "Hello"})
    return {"done": True}
```

流按写入顺序产生任意 Python 值。图失败时，已经排队的 chunk 会先被消费，然后原始异常由 async iterator 抛出。

如果消费者提前结束迭代，`stream()` 的清理逻辑会取消尚未完成的图执行任务。

## 最大步数

默认最大步数为 1024：

```python
graph.set_max_steps(100)
```

每次普通或内部节点成功执行并提交命令后，step 加一。达到上限后再次应用命令会抛出 `RecursionError`。该限制用于阻止未受控循环。

## 超时

```python
manager.add_node(slow_node, timeout=2.5)
```

- 超时只包围节点 `execute()`。
- 运行时会取消节点协程，并抛出包含节点名和秒数的 `TimeoutError`。
- 节点自身主动抛出的 `TimeoutError` 不会被错误标记为运行时 deadline。
- `None`、`0` 和负数表示不限制。

## 插件观察节点事件

图中的 `START`、节点名和 `END` 都会发布工作流事件。全局 namespace 直接使用节点名；命名图必须使用 `get_node_name_in_namespace()` 获得实际事件名。插件可以通过公共事件 API 在图节点处理器之前执行：

```python
from apix.core.event import ApixEvent, subscribe
from apix.core.graph import get_node_name_in_namespace


namespace = "agent-runtime"


@subscribe(
    get_node_name_in_namespace("model_call", namespace),
    priority=20,
)
async def enrich_model_context(event: ApixEvent) -> None:
    context = event.context
    context.state["system_policy"] = "safe"
```

图自动注册的节点处理器默认优先级是 `1`，因此更高优先级插件会先执行。也可使用 `between_handlers` 相对指定处理器插入。

`event.event_name` 是带 namespace 的事件路由名；原始图节点名保存在 `event.context.node_name`。如果插件要监听指定 namespace 下的一组节点，可以把 glob 节点模式传给辅助函数：

```python
@subscribe(
    get_node_name_in_namespace("agent.*", "agent-runtime"),
)
async def observe_agent_nodes(event: ApixEvent) -> None:
    original_node_name = event.context.node_name
```

传入 `namespace="*"` 可以生成监听所有非全局 namespace 中同名节点的模式。裸节点名或裸 glob 只适合全局事件或明确需要跨 namespace 匹配的插件。

## 分解图

```python
graph.decompose()
```

分解会：

- 注销图节点监听器；
- 注销通过 `graph.add_interrupted_hook` 注册的钩子；
- 释放命名空间；
- 使图拒绝新的 `invoke()`、`stream()`、`abort()` 等业务操作。

`decompose()` 幂等，但存在活跃调用时会拒绝执行。

## 继续阅读

- [状态模型、Command 与复制语义](./state.md)
- [GraphContext、快照、恢复与流式上下文](./context/README.md)
- [图中断与恢复控制](./interrupter/README.md)
