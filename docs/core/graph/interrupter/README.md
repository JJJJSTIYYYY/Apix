# 图中断与恢复控制

`apix.core.graph.interrupter` 用于在节点内部暂停图，向外部发布一个 `Block`，等待人工、工具或其他系统给出结果后继续执行。

该机制与 `NodeGraph.stream()` 相互独立：中断通过事件系统发布，流式 chunk 通过 `StreamWriter` 发布。

## 核心流程

1. 节点调用 `await interrupt(data=...)`。
2. 运行时创建一个 `Block`。
3. 运行时发布事件 `graph_{namespace}_interrupted`，其 `event.context` 为该 `Block`。
4. interruption hook 收到 `Block` 并把它交给外部决策流程。
5. 外部调用 `block.resolve(value)`。
6. `interrupt()` 返回 value，节点从暂停点继续执行。

如果外部调用 `block.cancel()`，当前图 attempt 会回到当前节点或并发批次执行前的最新快照并进入 `aborted`。

## 推荐用法：图拥有的 hook

```python
import asyncio

from apix.core.graph import GraphManager, START
from apix.core.graph.context import GraphContext
from apix.core.graph.interrupter import Block, interrupt


pending_reviews: asyncio.Queue[Block] = asyncio.Queue()


async def review_document(state: dict) -> dict:
    decision = await interrupt(
        data={
            "document_id": state["document_id"],
            "summary": state["summary"],
        }
    )
    return {"decision": decision}


graph = (
    GraphManager()
    .add_node(review_document)
    .add_edge(START, "review_document")
    .compile_graph(using_namespace="document-review")
)


@graph.add_interrupted_hook
async def capture_review(block: Block) -> None:
    await pending_reviews.put(block)


async def run() -> dict:
    context = GraphContext()
    invocation = asyncio.create_task(
        graph.invoke(
            {
                "document_id": "doc-1",
                "summary": "Draft summary",
            },
            context,
        )
    )

    block = await pending_reviews.get()
    block.resolve("approved")
    return await invocation
```

`graph.add_interrupted_hook` 自动选择图 namespace，并将 hook 纳入图生命周期。`graph.decompose()` 时会永久删除它，适合绝大多数场景。

## 全局 interrupted_hook

如果 hook 生命周期不属于某个 `NodeGraph`，可以直接注册：

```python
from apix.core.graph.interrupter import Block, interrupted_hook


@interrupted_hook(namespace="document-review", exist_ok=False)
async def on_document_review(block: Block) -> None:
    ...
```

对应事件名为：

```text
graph_document-review_interrupted
```

全局 namespace（`None` 或空字符串）对应：

```text
graph__interrupted
```

直接注册的 hook 不由图清理。卸载时使用：

```python
from apix.core.event import delete_handler_from_registry

delete_handler_from_registry(on_document_review.__name__)
```

## interrupt()

```python
await interrupt(
    *,
    data: Any = None,
    timeout: float | None = None,
    context: GraphContext | None = None,
) -> Any
```

参数：

| 参数 | 说明 |
| --- | --- |
| `data` | 发送给 hook 的任意本地对象，保存于 `Block.with_data` |
| `timeout` | 最大等待秒数；`None` 无限等待；超时返回 `None` |
| `context` | 可选 active `GraphContext`；节点内省略时自动读取当前 context |

节点外省略 `context` 会抛出 `RuntimeError`。即使显式传入 context，它也必须仍处于 active 调用中。

`interrupt()` 本身不创建额外快照。Graph Runtime 已在当前节点或并发批次执行之前自动保存快照，所以取消中断会回到本次调度之前的状态。

## Block

`Block` 是可 await 的冻结 dataclass：

| 成员 | 说明 |
| --- | --- |
| `run_id` | 所属图调用 attempt |
| `block_id` | 当前中断点唯一 id |
| `namespace` | 所属图 namespace |
| `with_data` | `interrupt(data=...)` 传入的数据 |
| `done` | Future 是否已经完成 |
| `cancelled` | Future 是否被取消 |
| `resolve(result)` | 让节点以 result 继续 |
| `cancel()` | 取消 Future，并触发当前 attempt abort |

`resolve()` 和 `cancel()` 都是一次性操作。Future 已完成后再次 `resolve()` 不产生效果。

应用在外部保存 Block 时，建议以 `(run_id, block_id)` 为唯一键，而不是只按 namespace 或 data 查找。

## 多次中断

同一个节点可以顺序调用多次：

```python
async def staged_review(state: dict) -> dict:
    first = await interrupt(data={"stage": 1})
    second = await interrupt(
        data={"stage": 2, "first_result": first}
    )
    return {"review_results": [first, second]}
```

每次调用生成不同 `block_id`，但属于同一 attempt，因此 `run_id` 相同。hook 必须逐个 resolve 对应 Block。

## 超时

```python
decision = await interrupt(
    data={"question": "continue?"},
    timeout=30,
)
```

30 秒内未 resolve 时：

- `interrupt()` 返回 `None`；
- Block 的 Future 被取消，`block.cancelled` 为 `True`；
- 图不会因为中断 timeout 自动 abort，而是从 `interrupt()` 后继续执行；
- 后续 `block.resolve(...)` 是 no-op。

如果 `None` 也是合法业务值，应在协议层让外部返回带状态的对象，或让节点把 timeout 的 `None` 显式转换成业务状态。

## 外部取消

```python
block.cancel()
```

外部取消的完整效果：

1. `Block` Future 被取消；
2. `interrupt()` 捕获该外部取消；
3. 所属 `GraphContext.abort()` 被调用；
4. 当前节点立即因 `CancelledError` 停止；
5. 下游节点不会运行；
6. `invoke()` 返回当前节点或并发批次执行前的最新快照状态。

运行时自身取消任务（例如节点 timeout、stream 消费者退出）与外部 `Block.cancel()` 会被区分，不会被误当作一次人工取消。节点 timeout 仍按 `TimeoutError` 向调用方传播。

## 与 stream() 组合

```python
async def review(state: dict) -> dict:
    writer = get_stream_writer()
    writer({"type": "review_requested"})
    decision = await interrupt(data=state["proposal"])
    writer({"type": "review_resolved", "decision": decision})
    return {"decision": decision}
```

stream 与 interrupt 的消费者不同：

- `async for chunk in graph.stream(...)` 消费 writer chunk。
- interruption hook 消费 `Block`。

两者可以同时工作。若 Block 被取消导致 abort，取消之前已经写入 StreamChannel 的 chunk 会先被迭代器产出，然后流结束。

## 生产环境建议

- hook 中不要长时间阻塞事件处理器；把 Block 放入业务队列后尽快返回。
- 保存并校验 `run_id` 与 `block_id`，防止旧审批结果 resolve 新调用。
- 为人工操作设置合理 timeout，并明确 timeout 的业务含义。
- 图分解或应用关闭前，处理仍未完成的 Block，避免调用永久悬挂。
- 不要把 Block 通过远程事件通道发送；它包含进程内 Future，只适合本地事件系统。
- 使用 `graph.add_interrupted_hook` 管理图专属 hook，减少替换图后旧 hook 残留。

