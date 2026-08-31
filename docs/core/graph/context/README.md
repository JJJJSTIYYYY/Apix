# GraphContext、快照、恢复与流式上下文

`GraphContext` 表示一次图调用尝试。它持有最新已提交状态、当前调度目标节点、step 计数、生命周期、快照历史，以及只在当前 attempt 中有效的 Future 和 stream writer。

## 创建与传入

最简单的调用不需要显式创建 context：

```python
result = await graph.invoke({"value": 1})
```

如果需要从外部 abort、检查快照或在失败后恢复，应保留 context：

```python
from apix.core.graph.context import GraphContext


context = GraphContext()
result = await graph.invoke({"value": 1}, context)
```

也可以为本次调用指定 state schema：

```python
context = GraphContext(MyState)
```

如果 context 没有显式 schema，首次调用时会采用编译图的默认 schema。显式 schema 不会被图默认值覆盖。

## 生命周期

`GraphContext.status` 的状态转换如下：

其公开类型别名 `GraphContextStatus` 为 `Literal["pending", "running", "failed", "aborted", "finished"]`。

| 当前状态 | 允许进入 | 含义 |
| --- | --- | --- |
| `pending` | `running`、`failed`、`aborted` | 尚未开始的新 context |
| `running` | `finished`、`failed`、`aborted` | 已绑定一次调用 |
| `finished` | 无 | 正常到达 `END` |
| `failed` | 无 | 调用发生异常 |
| `aborted` | 无 | 调用被外部或中断控制取消 |

终态 context 不能再次执行。恢复会创建新的 `pending` context，而不是重置原对象。

常用只读属性：

| 属性 | 说明 |
| --- | --- |
| `status` | 当前生命周期状态 |
| `is_consumed` | 是否已经开始过一次调用 |
| `is_bound` | 是否具有 run id、completion 和 writer |
| `is_active` | 是否 running、绑定完整且 completion 未完成 |

运行字段：

| 字段 | 说明 |
| --- | --- |
| `run_id` | 当前 attempt 的唯一 id，绑定时以 `graph-` 前缀生成 |
| `state` | 最新已提交状态 |
| `target_node_name` | 当前调度目标节点；快照中表示恢复后应重新执行的目标节点 |
| `steps` | 已完成并提交的节点执行次数 |
| `context_snapshot` | 按时间顺序保存的快照列表 |

`completion`、`stream_writer` 和 `_context_namespace` 是运行时绑定细节。用户通常通过公开属性、访问函数和快照接口使用它们，而不直接修改。

## 快照时机

`NodeGraph` 在每个普通节点或内部 router/condition 节点执行之前自动调用 `take_a_snapshot()`。`START` 和 `END` 不创建快照。

快照形状：

```python
class GraphContextSnapshot(TypedDict):
    timestamp: float
    state: dict[str, Any]
    target_node_name: str
    steps: int
    namespace: str
```

语义：

- `state` 是待执行节点之前的最后已提交状态。
- `target_node_name` 是恢复后应重新执行的目标节点。
- `steps` 是此前已经完成的 step 数。
- `namespace` 限制恢复只能发生在原命名空间。
- 快照会深拷贝完整 state，包括 `KeepRef` 字段。

因此，失败节点恢复后会从节点执行前状态重新执行该节点，而不会包含失败节点的未提交修改。

## 手动读取快照

```python
latest = context.get_snapshot()
first = context.get_snapshot(0)
previous = context.get_snapshot(-2)
history = context.get_all_snapshots()
```

- `get_snapshot()` 默认返回最新快照。
- 没有快照时返回 `None`。
- `get_all_snapshots()` 返回整个历史列表。
- 返回值均为深拷贝，修改它们不会改变 context 内保存的历史。
- 越界版本沿用 Python list 的 `IndexError`。

`take_a_snapshot()` 是公开方法，但只允许在 active 且已绑定 namespace 的 context 上调用。一般由运行时自动管理；应用只有在自定义执行流程确实需要额外 checkpoint 时才应手动调用。

## 从最新快照恢复

标准恢复流程：

```python
from apix.core.graph.context import GraphContext


context = GraphContext()

try:
    await graph.invoke(initial_state, context)
except Exception:
    recovered = GraphContext.from_snapshot(
        context.context_snapshot
    )
    result = await graph.invoke(recovered.state, recovered)
```

`from_snapshot()` 接受单个 snapshot 或 snapshot list：

```python
GraphContext.from_snapshot(snapshot)

GraphContext.from_snapshot(
    snapshots,
    version=-1,
)
```

恢复对象具有以下特征：

- `status == "pending"`；
- 新的 attempt 尚无 `run_id`、completion 或 writer；
- state、`target_node_name`、steps 与选中快照一致；
- 整个保留历史被再次深拷贝；
- 运行时绑定字段不会从旧 attempt 复制。

调用恢复 context 时，应将 `recovered.state` 作为 `invoke()` 或 `stream()` 的 state 参数。绑定过程会以传入 state 作为本次 attempt 的初始状态。

## 从指定版本分支恢复

```python
recovered = GraphContext.from_snapshot(
    context.context_snapshot,
    version=1,
)
```

`version` 使用原生 Python list 索引：

- `0` 是第一份快照；
- `-1` 是最新快照；
- `-2` 是倒数第二份；
- 越界抛出 `IndexError`；
- 非整数索引抛出 `TypeError`。

从较旧版本恢复会创建一个新分支：选中版本之后的快照不会进入 recovered history；选中快照及其之前的历史会被保留。随后运行产生的新快照追加到该分支。

当传入单个 snapshot 而不是 list 时，`version` 被忽略。

## Schema 与恢复

快照不保存 schema class。恢复时有两种策略：

```python
# Adopt the compiled graph's default schema on invocation.
recovered = GraphContext.from_snapshot(snapshots)

# Explicitly select a schema for the recovered branch.
recovered = GraphContext.from_snapshot(
    snapshots,
    state_schema=MyState,
)
```

省略 schema 时，未消费的 recovered context 会在调用时采用替代图的默认 schema。这允许在同一 namespace 上用新的编译图恢复，同时继续获得它定义的 `AutoMerge` 和 `KeepRef` 行为。

## 命名空间限制与替代图

快照属于 namespace，而不是某个具体 `NodeGraph` 实例：

- 可以分解旧图，再在相同 namespace 编译替代图并恢复。
- 不能把 recovered context 传给不同 namespace 的图。
- 替代图必须仍然包含快照 `target_node_name` 对应的节点，否则发布恢复入口时抛出 `ValueError`。

```python
old_graph.decompose()

replacement = (
    GraphManager(State)
    .add_node(retryable_node, "work")
    .add_edge(START, "work")
    .compile_graph(using_namespace="shared-runtime")
)

recovered = GraphContext.from_snapshot(old_context.context_snapshot)
result = await replacement.invoke(recovered.state, recovered)
```

## abort()

可以直接调用：

```python
context.abort()
```

也可以经由图验证所有权后调用：

```python
await graph.abort(context)
```

active 调用 abort 后：

- `invoke()` 立即以最新快照状态完成；
- `stream()` 会先产出已经排队的 chunk，再结束；
- 当前节点可能在后台继续运行，但它的结果不会被提交，也不会继续路由；
- context 进入 `aborted`；
- abort 幂等。

因为自动快照在节点执行前创建，abort 返回的是当前节点之前的状态。若还没有快照，则回退到当前 live state。

对尚未绑定的 pending context 调用 `abort()` 只把它置为 `aborted`，没有 completion 可返回；此 context 随后不能用于图调用。

`finished` 或 `failed` context 不能再 abort。

## 节点内访问当前上下文

Graph Runtime 在节点执行期间通过 `ContextVar` 绑定当前 `GraphContext`：

```python
from apix.core.graph.context import (
    get_current_namespace,
    get_current_run_id,
    get_graph_context,
    get_stream_writer,
)


async def node(state: dict) -> dict:
    context = get_graph_context()
    run_id = get_current_run_id()
    namespace = get_current_namespace()
    writer = get_stream_writer()

    writer({"run_id": run_id, "namespace": namespace})
    return {}
```

这些函数只能在节点执行上下文中使用：

- 图外调用会抛出 `RuntimeError`。
- `get_stream_writer()` 在 `invoke()` 中返回可复用的 no-op writer，因此节点可以无条件发出 chunk；只有 `stream()` 调用方会收到内容。
- 由节点创建的 asyncio task 会按照 Python `ContextVar` 规则继承创建时上下文，但任务不应在图 attempt 结束后继续使用 context 或 writer。

`apix_graph_context(context)` 是底层 context manager，主要供 Graph Runtime 或自定义 `BaseNode` 执行框架绑定上下文。普通节点无需手动使用。

## StreamWriter 与 StreamChannel

`StreamWriter` 是同步 callable：

```python
writer(chunk)
writer.write(chunk)
```

`StreamChannel` 是单消费者异步迭代器，并暴露 `.writer`：

```python
channel = StreamChannel()
channel.writer("first")
channel.close()

chunks = [chunk async for chunk in channel]
```

关闭行为：

- `close()` 幂等。
- 关闭前已经排队的 chunk 仍会按 FIFO 读取。
- 关闭后继续写入抛出 `RuntimeError`。
- writer 使用当前事件循环内的 `asyncio.Queue.put_nowait()`；不要从其他线程直接调用。

一般应用只使用 `NodeGraph.stream()` 和 `get_stream_writer()`，无需直接创建 `StreamChannel`。

`noop_stream_writer()` 返回全局可复用的丢弃型 writer，`NodeGraph.invoke()` 使用它统一节点接口。自定义运行器在不需要实际流式输出时也可以使用该函数。

## 快照持久化注意事项

`GraphContextSnapshot` 被设计为可存储 checkpoint，但 `state` 的具体值是否可序列化由应用负责：

- 内存恢复只要求对象支持 `deepcopy`。
- JSON、数据库或消息队列持久化还要求 state 值可由对应格式编码。
- Future、锁、打开的客户端和文件句柄通常不适合进入持久快照。
- 如果运行资源必须放在 state 中，可使用 `KeepRef` 避免节点 deepcopy，但自动快照仍会 deepcopy 它；应提供可复制表示或把可恢复描述与实时资源分离。
