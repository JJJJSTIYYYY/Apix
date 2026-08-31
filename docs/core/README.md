# APIX Core Runtime

`apix.core` 是 APIX 的底层运行时，包含两套相互协作但职责清晰的基础设施：

- `apix.core.event`：异步事件发布、通配符订阅、确定性排序、处理器链版本隔离，以及本地或远程事件通道。
- `apix.core.graph`：基于事件系统驱动的状态图，包括节点、路由、状态合并、流式输出、运行上下文、快照恢复与人在环中断。

`apix.core.utils` 目前主要定义 Core Runtime 对外抛出的异常类型。

## 模块结构

```text
apix/core/
├── event/
│   ├── base.py               # Event and handler data models
│   ├── event_loop.py         # Event consumption and dispatch
│   ├── event_pipe.py         # Local and remote channels
│   ├── event_registry.py     # Observed exact event names
│   └── handler_registry.py   # Subscription, ordering, and chain versions
├── graph/
│   ├── base.py               # Markers, Command, START, and END
│   ├── graph_manager.py      # Fluent graph builder
│   ├── node.py               # BaseNode, Node, and ParallelNode
│   ├── node_graph.py         # Compiled graph runtime
│   ├── context/
│   │   ├── graph_context.py  # Lifecycle and snapshots
│   │   ├── manager.py        # Invocation-local ContextVar access
│   │   └── stream_writer.py  # Streaming channel and writer
│   └── interrupter/
│       ├── base.py           # Block
│       └── graph_interrupter.py
└── utils/
    └── exception.py
```

## 运行模型

Graph Runtime 并不在 `NodeGraph` 对象中保存每次调用的状态。一次调用的状态由 `GraphContext` 持有，并通过统一的图调度事件驱动执行：

1. `GraphManager` 编译图时，为当前 namespace 注册一个通用 `GRAPH_DISPATCH` handler。
2. `NodeGraph.invoke()` 或 `NodeGraph.stream()` 创建并绑定一次调用的 `GraphContext`。
3. 运行时把 `START` 写入 `GraphContext.target_node_name`，并向 `EVENT_PIPE` 发布 namespace 隔离后的 `GRAPH_DISPATCH` 事件。
4. 全局 `APIX_EVENT_LOOP` 消费事件，通用 dispatch handler 根据 `target_node_name` 选择并执行目标节点。
5. 节点返回 `dict` 或 `Command`；运行时提交状态、更新下一个 `target_node_name`，再发布同一个 dispatch 事件。
6. 当目标变为 `END` 时，dispatch handler 将最终状态写入完成 Future，调用方得到结果。

这套模型带来两个重要性质：

- 同一个编译图可以并发执行多次，因为状态和节点路由目标都由调用级 `GraphContext` 隔离。
- 事件系统只负责图级 dispatch 和 namespace 隔离，不再用具体节点名承担内部路由职责；插件需要观察节点调度时，可订阅 `GRAPH_DISPATCH` 并检查 `event.context.target_node_name`。

## 最小示例

以下示例创建 `prepare -> answer -> END` 图。事件循环会在第一次调用时自动启动。

```python
import asyncio
from typing import Annotated, TypedDict

from apix.core.graph import AutoMerge, END, GraphManager, START


class AgentState(TypedDict, total=False):
    prompt: str
    history: Annotated[list[str], AutoMerge()]
    answer: str


def prepare(state: AgentState) -> dict:
    return {"history": [f"user:{state['prompt']}"]}


async def answer(state: AgentState) -> dict:
    await asyncio.sleep(0)
    return {
        "answer": state["prompt"].upper(),
        "history": ["assistant:done"],
    }


async def main() -> None:
    graph = (
        GraphManager(AgentState)
        .add_nodes([prepare, answer])
        .add_edge(START, "prepare")
        .add_edge("prepare", "answer")
        .add_edge("answer", END)
        .compile_graph(using_namespace="quickstart")
    )

    try:
        result = await graph.invoke(
            {"prompt": "hello", "history": []}
        )
        print(result)
    finally:
        graph.decompose()


asyncio.run(main())
```

预期结果中的 `history` 会被 `AutoMerge` 合并：

```python
{
    "prompt": "hello",
    "history": ["user:hello", "assistant:done"],
    "answer": "HELLO",
}
```

## 常用导入

### 事件系统

```python
from apix.core.event import (
    APIX_EVENT_LOOP,
    APIX_EVENT_REGISTRY,
    APIX_HANDLER_REGISTRY,
    EVENT_PIPE,
    ApixEvent,
    EventType,
    delete_handler_from_registry,
    get_handler_meta,
    get_unmatched_subscriptions,
    subscribe,
    unsubscribe,
)
```

### 图运行时

```python
from apix.core.graph import (
    AutoMerge,
    BaseNode,
    Command,
    END,
    GraphManager,
    KeepRef,
    Node,
    NodeGraph,
    ParallelNode,
    Reset,
    START,
)

from apix.core.graph.context import (
    GraphContext,
    get_current_namespace,
    get_current_run_id,
    get_graph_context,
    get_stream_writer,
)

from apix.core.graph.interrupter import (
    Block,
    interrupt,
    interrupted_hook,
)
```

## 生命周期管理

### 全局事件运行时

`NodeGraph` 会在调用时执行 `APIX_EVENT_LOOP.start()`，因此一般不需要手动启动事件循环。应用关闭或测试收尾时应主动停止事件循环：

```python
from apix.core.event import APIX_EVENT_LOOP, EVENT_PIPE


async def shutdown_core_runtime() -> None:
    await EVENT_PIPE.join()
    await APIX_EVENT_LOOP.stop()
    await EVENT_PIPE.stop()
```

如果应用使用远程 `mailbox` 或 `mailtruck` 通道，应在启动阶段先执行 `await EVENT_PIPE.start()`，否则外部连接和邮箱转发任务不会建立。

### 编译图

每个已编译图会占用一个 dispatch listener 命名空间。使用完成后调用 `graph.decompose()`，或使用同步上下文管理器：

```python
with (
    GraphManager()
    .add_node(lambda state: {"done": True}, "work")
    .add_edge(START, "work")
    .compile_graph(using_namespace="temporary")
) as graph:
    result = await graph.invoke({})
```

正在执行调用的图不能被分解。`decompose()` 成功后会注销图拥有的通用 dispatch handler 和中断钩子，并释放命名空间；该 `NodeGraph` 不能再次调用。

## 并发边界

- 不同事件实例会由独立分发任务处理，最多同时存在 100 个事件分发任务。
- 后台事件处理器另有 100 个任务的并发限制。
- 同一个 `NodeGraph` 可并发调用；普通字段会按深拷贝隔离。
- `KeepRef` 会刻意破坏字段级深拷贝隔离，因此不推荐在并发调用中共享可变对象。
- `ContextVar` 绑定在节点执行期间有效。由节点创建的 asyncio task 会继承当前上下文；若任务生命周期超过节点，应避免继续使用已经结束或关闭的运行资源。
- 编译图的命名空间必须唯一，除非使用 `exist_ok=True` 显式替换一个当前无活跃调用的图。

## 文档导航

- [事件系统](./event/README.md)
- [处理器注册、排序与版本隔离](./event/handlers.md)
- [事件通道、序列化与远程传输](./event/channels.md)
- [Graph Runtime](./graph/README.md)
- [状态模型、Command 与复制语义](./graph/state.md)
- [GraphContext、快照、恢复与流式上下文](./graph/context/README.md)
- [图中断与恢复控制](./graph/interrupter/README.md)
- [Core 异常类型](./utils/README.md)
