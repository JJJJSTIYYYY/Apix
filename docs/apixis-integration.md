# Apixis 接入指南

## 安装与启动

后端要求 Python 3.12 或更高版本。依赖声明为 `apixis>=1.0.0`，`source/uv.lock` 锁定验证使用的版本 `1.1.0`。当前接入使用 1.1.0 的本地事件运行时，不依赖旧版远程通道。

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

`ToolNode` 直接继承 Apixis 的 `BaseNode`。工具只返回业务结果；节点并发执行整批工具，等待全部完成后，将每个结果通过 `str()` 转成字符串，按调用顺序生成 `ApixToolMessage`，并返回一个包含全部消息更新的 `Command`。

```python
from apix.agent.core.tool import ToolNode, tool

@tool
async def calculate(left: int, right: int) -> int:
    return left + right

# Bind at construction, using a node name or an Apixis BaseNode instance.
tools = ToolNode([calculate], bind_llm_node="model")

# Bind, replace, or clear the target after construction.
tools.bind_llm_node("model")
# tools.bind_llm_node(model_node)
# tools.bind_llm_node(None)
```

| 接口 / 行为 | 说明 |
| --- | --- |
| `ToolNode(tool_set, name="tools", messages_key="messages", timeout=None, *, bind_llm_node=None)` | 注册工具，并可绑定工具执行后的 LLM 节点 |
| `bind_llm_node(llm_node)` | 接受非空节点名或 Apixis 节点对象，替换绑定并返回自身；`None` 清除绑定 |
| `get_schemas(filter_names=None)` | 按注册顺序返回工具 schema 副本，可按名称过滤 |
| 有工具调用 | 返回 `Command(update={messages_key: tool_messages}, goto=绑定节点名)`，下一节点只执行一次 |
| 未绑定 LLM 节点 | 工具照常执行，返回的 `Command.goto` 为 `None`，当前分支结束 |
| 没有工具调用 | 返回空列表，当前分支结束，即使已经绑定 LLM 节点 |

所有返回类型均作为普通结果转成字符串，包括 `None`、字典、`ApixToolMessage` 和 `Command`。工具返回的 `Command.update`、`Command.goto` 不再用于更新图状态或路由；需要业务状态更新时，可由图中的其他节点处理工具消息，或通过注入上下文操作共享业务对象。

节点会为每条新消息填入真实的工具调用 ID、工具名和执行耗时，不修改工具返回的对象。任一工具失败或节点被取消时，节点取消并等待其他未完成工具，然后向外传播异常。MCP 工具的 `tool_calls` 生命周期覆盖完整批次，批次结束后释放资源。

`AgentGraphCreator(State, messages_key="conversation").add_tools([...], bind_llm_node="model")` 会将自定义消息字段与绑定目标传给 ToolNode。完整的模型→工具→模型流程可参考 `source/tests/integration/test_complete_agent_integration.py`。

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

从 `source` 目录运行时，Apix 复用 Apixis 对 `./config.yaml` 的加载结果。Agent、LLM、缓存及数据存储设置由 Apix 使用；本地事件队列容量、事件背压、日志及 `SERVER.base_dir` 由 Apixis 读取。`SERVER.base_dir` 默认为 `./.apix/`：Apix 将其作为 `APIX_BASE_DIR`，SQLite 默认数据库、文件存储及内置缓存使用此目录；Apixis 将 `APIXIS_BASE_DIR` 设为该目录下的 `apixis` 子目录，用于自身日志。

- `PIPELINE.event_loop_backpressure` 是有效键名，旧的 `event_loop_back_pressure` 已更正。
- `PIPELINE.event_handler_default_time_out` 已删除；处理器超时通过订阅的 `time_out` 设置。
- 事件仅通过有界的进程内 `BuiltinChannel` 队列传递，容量由 `PIPELINE.event_pipe_max_len` 设置，不再支持 Kafka、RabbitMQ 或 HTTP 远程事件传输。
- `REMOTE_GATEWAY`、`EVENT_CHANNEL` 和远程节点身份配置已失效；遗留配置不会启用远程模式，也不会限制 SQLite 或内置缓存的使用。
- HTTP 健康检查返回 `{"status": "ok", "service": "apix"}`，不再导入已删除的 `NODE_ID`。
- Apix 日志使用 Apixis 的 Logger；服务生命周期统一启动和关闭日志。

HTTP 服务显式等待 `start_core()`，关闭时依次停止事件管道、应用服务、事件消费者和日志。独立脚本调用 Apixis 的 getter 会自动唤起核心运行时；显式管理服务生命周期时，应保留组件引用后调用它们的 `stop()`。

运行环境：asyncio。默认测试不需要模型 API、外部 MCP、MySQL 或 Redis；这些外部服务的在线连通性需在部署环境验证。Apixis 事件集成测试验证本地队列、服务生命周期重启和健康检查，不再验证远程传输身份。Apix 自身仍使用 `httpx` 调用模型及测试 ASGI 接口，这与已删除的 Apixis 远程传输无关。
