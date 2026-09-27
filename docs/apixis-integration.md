# Apixis 接入指南

## 安装与启动

后端要求 Python 3.12 或更高版本。项目已执行 `uv add apixis`，依赖声明为 `apixis>=1.0.0`，`source/uv.lock` 锁定验证使用的版本 `1.0.0`。

```bash
cd source
uv sync --locked
uv run pytest
uv run python -m apix.server
```

升级依赖后应重新运行测试：`uv lock --upgrade-package apixis && uv sync --locked`。

## 导入与职责

`apix.core` 已删除，不提供兼容转发模块。事件与图类型直接从 Apixis 导入：

```python
from apixis.core.event import get_event_pipe, subscribe, unsubscribe
from apixis.core.graph import Command, AutoMerge, GraphManager, get_stream_writer
from apix.agent.core.graph import AgentGraph, AgentGraphCreator
from apix.agent.core.tool import ToolNode, tool
```

Apix 的 AgentGraph 扩展 Apixis 的 NodeGraph，负责调用结束时关闭当前 run 的 MCP 资源；底层调度、命名空间和上下文管理全部由 Apixis 提供。需要这种资源清理的 Agent 使用 `AgentGraphCreator`。

## 创建 Agent 图

编译时指定入口，后续执行目标全部由节点返回的 `Command.goto` 指定。

```python
from typing import Annotated, TypedDict
from apixis.core.graph import AutoMerge, Command
from apix.agent.core.graph import AgentGraphCreator

class State(TypedDict):
    messages: Annotated[list[str], AutoMerge()]

def prepare(state: State) -> Command:
    return Command(update={"messages": ["ready"]}, goto="respond")

def respond(state: State) -> Command:
    return Command(update={"messages": ["done"]})

graph = (
    AgentGraphCreator(State)
    .add_nodes([prepare, respond])
    .compile_agent("prepare")
)

# Run inside asyncio.
# result = await graph.invoke({"messages": []})
# graph.decompose()
```

| 接口 | 用法 |
| --- | --- |
| `compile_agent(entry_point, *, using_namespace=None, exist_ok=False)` | 编译 AgentGraph；入口为节点名、并发节点列表或 `None` |
| `compile_graph(...)` | 与 `compile_agent(...)` 相同，也返回 AgentGraph |
| `Command(goto="node")` | 执行下一个节点 |
| `Command(goto=["a", "b"])` | 执行下一组并发节点 |
| `Command(goto=None)` / `Command(goto=[])` | 当前分支结束 |
| 返回普通字典 | 更新状态并结束当前分支 |

不再使用 `START`、`END`、`add_edge()` 或条件边。未指定命名空间时，Apixis 自动分配进程内唯一命名空间。

## 工具节点

`ToolNode` 直接继承 Apixis 的 `BaseNode`。它并发调用工具，按照调用列表顺序返回 `Command` 列表。

工具返回普通字符串或 `ApixToolMessage` 时，生成的 Command 没有下一跳。若工具完成后需要继续调用模型，应明确返回带 `goto` 的 Command：

```python
from apix.agent.core.tool import tool
from apix.agent.core.utils.message import ApixToolMessage
from apixis.core.graph import Command

@tool
async def calculate(left: int, right: int) -> Command:
    return Command(
        update={"messages": [ApixToolMessage(
            content=str(left + right), tool_call_id="placeholder"
        )]},
        goto="model",
    )
```

`ToolNode` 会填入真实的工具调用 ID、工具名和执行耗时。多个工具返回同一个下一跳时，Apixis 合并为一个执行目标。没有工具调用时返回空列表，图结束。完整的模型→工具→模型流程可参考 `source/tests/integration/test_complete_agent_integration.py`。

`AgentGraphCreator(State, messages_key="conversation").add_tools([...])` 会将自定义消息字段传给 ToolNode。工具返回 Command 时也需在同名字段中提供消息更新。

## 上下文、快照与流式调用

```python
context = graph.create_context({"messages": []})
# result = await graph.invoke(graph_context=context)
# restored = graph.restore_context(context.get_snapshot())
# result = await graph.invoke(graph_context=restored)
```

只能传 `state` 或 `graph_context` 中的一个。上下文归创建它的图所有；恢复也通过该图完成。恢复执行从快照目标节点开始。

提前停止消费流时，应显式关闭迭代器：

```python
from contextlib import aclosing

# async with aclosing(graph.stream({"messages": []})) as stream:
#     async for chunk in stream:
#         print(chunk)
#         break
```

AgentGraph 在正常完成、异常、取消及流关闭后清理本次调用的 MCP 资源；被拒绝的重复调用不会清理原调用的资源。

## 配置与生命周期

从 `source` 目录运行时，Apix 和 Apixis 均读取 `./config.yaml`。Agent、LLM、缓存及数据存储设置由 Apix 使用；事件通道与事件背压设置由 Apixis 使用。

- `PIPELINE.event_loop_backpressure` 是有效键名，旧的 `event_loop_back_pressure` 已更正。
- `PIPELINE.event_handler_default_time_out` 已删除；处理器超时通过订阅的 `time_out` 设置。
- `REMOTE_GATEWAY` 和 `EVENT_CHANNEL` 保留，供 Apixis 远程通道读取；现有 mailbox 前缀保持不变。
- HTTP 健康检查使用 Apixis 的 `NODE_ID`，与事件传输身份一致。
- Apix 日志使用 Apixis 的 Logger；服务生命周期统一启动和关闭日志。

HTTP 服务显式等待 `start_core()`，关闭时依次停止事件管道、应用服务、事件消费者和日志。独立脚本调用 Apixis 的 getter 会自动唤起核心运行时；显式管理服务生命周期时，应保留组件引用后调用它们的 `stop()`。

运行环境：asyncio。测试不需要模型 API、外部 MCP、MySQL、Redis、Kafka 或 RabbitMQ；这些外部服务的在线连通性需在部署环境验证。
