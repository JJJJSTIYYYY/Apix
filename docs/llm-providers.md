# LLM Provider 适配层

Bot 层只负责模型推理。会话历史、工具执行和 Agent 循环由 Apix 管理。
Protocol 负责发送请求，Codec 负责消息转换，Provider/Model Profile 用于描述不同服务商和模型的 API 差异。

全部内置服务商的官方来源、型号差异和兼容边界见
[Bot 官方文档核对记录](llm-provider-audit.md)（2026-10-07）。

## 调用模型

```python
from apix.agent.core.bot import Bot
from apix.agent.core.utils.message import ApixUserMessage

async with Bot(
    provider="deepseek",
    model="deepseek-v4-flash",
    api_key=api_key,
) as bot:
    response = await bot.invoke(
        [ApixUserMessage(content="你好")],
        reasoning=True,
        reasoning_effort="high",
    )
```

`invoke()` 返回 `ApixAiMessage`，`stream()` 逐块产出 `ApixAiMessageChunk`。
`Response` 和 `StreamEvent` 分别是这两个现有 Apix 类型的公开别名。
可使用 `ApixAiMessageAccumulator` 聚合消息块。流被截断时会抛出
`ProviderResponseError`，不会将不完整的响应视为已完成。

当 Profile 的推理模式为 `optional` 或 `always` 时，默认启用推理。
未配置推理能力的 Profile 不会携带推理控制参数，这不代表上游模型一定没有内部思考。
不支持的推理强度、消息角色、无效的工具选择，
以及尝试关闭始终推理模型的推理能力，都会在发送网络请求前触发异常。
只有显式配置推理强度别名，才能将调用方指定的强度映射到另一个等级。
部分 Qwen3 型号的思考模式只支持流式调用；Anthropic 的 effort 则可以在关闭思考时独立使用。

用量信息保存在 `response.metadata["usage"]` 中，按服务商提供的信息包含
`input_tokens`、`output_tokens` 和 `total_tokens`。
Anthropic 的缓存输入 token 和 Gemini 的思考 token 会计入统一后的统计。
推理文本通过 `response.reasoning` 获取。需要原样保留的推理块和签名存放在
`response.extensions` 中，流式调用后也会保留，以便由客户端管理历史回传。

## 函数工具

```python
from apix.agent.core.tool import tool
from apix.agent.core.utils.message import ApixToolMessage

@tool
def lookup_city(city: str) -> str:
    """在 Apix 的数据源中查询指定城市。"""
    return city

messages = [ApixUserMessage(content="查询巴黎")]
first = await bot.invoke(messages, tools=[lookup_city])
messages.append(first)
for call in first.tool_calls:
    result = await lookup_city.func(**(call["args"] or {}))
    messages.append(ApixToolMessage(
        tool_call_id=call["call_id"], name=call["tool_name"], content=str(result),
    ))
second = await bot.invoke(messages, tools=[lookup_city])
```

上例直接执行单个工具；Agent 通常将工具执行交给 `ToolNode`。
`bind_tools()` 也接受 `ToolNode`，对 `ToolNode` 和可迭代工具集合都会应用权限过滤。
在单次调用中传入 `tools=[]`，可禁用该次调用的已绑定工具。工具 Schema 会在使用前复制。

`tool_choice` 接受 `auto`、`none`、`required` 或已绑定函数的名称。
`parallel_tool_calls` 会根据模型能力进行校验，且仅在协议能够表达所请求的设置时编码到请求中。
Ollama 原生协议支持自动选择工具；Gemini 不提供关闭并行工具调用的开关。

不接受服务商原生的搜索、检索、MCP、计算机操作或代码执行工具。
传给 Bot 的工具必须是 Apix `Tool` 对象，或来自 `ToolNode`。
Bot 不执行工具，也不会在内部启动 Agent 循环。

## 注册服务商与模型

接入普通兼容服务商只需注册 Provider Profile：

```python
from apix.agent.core.bot import REGISTRY, ProviderProfile

REGISTRY.register_provider(ProviderProfile(
    name="example",
    protocol="openai",
    endpoint="https://api.example.com/v1",
))
bot = Bot(provider="example", model="example-chat", api_key=api_key)
```

也可以将 `ProviderProfile` 直接传给 `Bot(provider=...)`。
未知模型使用协议的基础默认配置，不启用推理能力。
Model Profile 按服务商隔离，使用不区分大小写的 glob 模式匹配模型名。
精确匹配优先，其次按模式的具体程度排序；同优先级的匹配会触发歧义错误。
可注册更具体的模式来覆盖已有模型系列的配置。

```python
from apix.agent.core.bot import ModelProfile, ReasoningProfile, RequestField, ToolProfile

REGISTRY.register_model("example", ModelProfile(
    pattern="example-r1*",
    api_style="chat_completions",
    reasoning=ReasoningProfile(
        mode="always",
        effort_values=("low", "high"),
        effort_map={"medium": "high"},
        effort=RequestField(("reasoning_effort",)),
        replay="when_tools",
    ),
    tools=ToolProfile(reasoning_choice_modes=("auto",)),
))
```

内置服务商包括 OpenAI、DeepSeek、MiMo（`xiaomimimo` 是其别名）、MiniMax、
Moonshot、Z.AI、Qwen、Anthropic、Gemini、OpenRouter、SiliconFlow 和原生 Ollama。
每个内置服务商都有对应的轻量构造入口，可从 `apix.agent.core.bot` 导入：

| Provider | Bot 类 |
| --- | --- |
| `openai` | `OpenAIBot` |
| `deepseek` | `DeepSeekBot` |
| `mimo` / `xiaomimimo` | `XiaomiMIMOBot` |
| `minimax` | `MiniMaxBot` |
| `moonshot` | `MoonshotBot` |
| `zai` | `ZAIBot` |
| `qwen` | `QwenBot` |
| `anthropic` | `AnthropicBot` |
| `gemini` | `GeminiBot` |
| `openrouter` | `OpenRouterBot` |
| `siliconflow` | `SiliconFlowBot` |
| `ollama` | `OllamaBot` |

例如 `GeminiBot(model=..., api_key=...)` 等价于
`Bot(provider="gemini", model=..., api_key=...)`，会自动使用注册的协议和模型配置。
这些类只指定默认 `provider`，不复制传输逻辑或模型能力配置。

经过官方文档核对、但未完成真实联调的兼容性 Profile 仍标记为 `community`。
没有持续的真实服务商 CI 测试覆盖时，不会将服务商标记为 `verified`。
内置配置只为已确认的型号或模式声明能力，不保证所有上游变体行为都相同；
必要时应为具体变体注册专用 Profile。旧型号配置的保留不代表上游仍可调用。

## 自定义 Profile 与 Schema

配置按以下顺序解析，后者覆盖前者：

1. 协议默认配置。
2. 服务商地址与协议。
3. 匹配到的 Model Profile。
4. `CustomProfile` 中显式指定的字段。
5. 单次调用参数与请求选项。

只覆盖端点地址时，会保留匹配到的模型行为配置：

```python
from apix.agent.core.bot import CustomProfile

bot = Bot(
    provider="deepseek", model="deepseek-v4-flash", api_key=api_key,
    custom_profile=CustomProfile(endpoint="https://proxy.example.com/v1"),
)
```

`CustomBot(model=..., endpoint=..., api_key=...)` 默认使用 OpenAI Chat Completions。
接入其他受支持协议时，可设置 `CustomProfile(protocol=..., api_style=...)`。
`model_profile=` 会替换匹配到的整个 Model Profile；
`CustomProfile(reasoning=..., tools=..., messages=..., response_schema=..., request_options=...)`
只替换对应的配置组。配置组对象按完整值替换；只修改组内某个字段时，可使用 `dataclasses.replace()`。

Schema 使用由键名或索引组成的元组路径、类型选择器和事件判别字段：

```python
from apix.agent.core.bot import ResponseField, ResponseLayout, ResponseSchema, StreamField

schema = ResponseSchema(
    complete=ResponseLayout(
        content=("result", "text"),
        reasoning=ResponseField(("result", "blocks"), {"type": "thought"}, ("text",)),
        usage=("meta", "usage"),
        finish_reason=("meta", "finish_reason"),
    ),
    stream=ResponseLayout(
        content=StreamField(("type",), "text.delta", ("delta",)),
        finish_reason=StreamField(("type",), "done", ("finish_reason",)),
    ),
)
```

`ResponseField.value` 可以继续嵌套另一个 `ResponseField`，用于处理嵌套的类型化集合。
实现不会猜测推理字段，也不依赖 JSONPath。
`ReasoningProfile.output` 和 `stream_output` 可显式覆盖推理内容的选择器。
`replay` 决定是否回传历史推理内容，与输出位于哪个字段相互独立。
`when_tools` 根据当前请求是否携带函数工具判断，而非逐条判断历史消息是否有 `tool_calls`。
Schema 的 `extension_stream_fields` 可声明按块索引或 ID 拼接的字符串字段；
未声明的扩展字段保持快照语义。

## 调用策略

`InvocationPolicy` 管理超时、重试、流式用量统计和普通请求参数的默认值。
`ModelProfile.request_options` 提供模型的普通请求默认值，之后依次合并策略请求选项、
`request_options=` 和兼容参数 `extra_body=`，且不会修改原始配置。
请求构建器统一生成最终请求体，SDK 特有的扩展参数路由只在传输层处理。

Apix 要求 `store=False` 且 `use_server_state=False`。
不能通过原始请求选项覆盖上下文结构、工具、状态或推理控制字段，
应使用显式的消息、工具和推理参数。
需要 OpenAI 推理摘要时，可在策略中设置
`request_options={"reasoning": {"summary": "auto"}}`。

Bot 内部创建的客户端由 `async with bot` 或 `await bot.aclose()` 关闭。
注入的客户端仍由调用方管理。关闭或取消流时，会释放对应的传输迭代器。

## 迁移与测试

旧的 `OpenAIBot`、`DeepSeekBot`、`MiniMaxBot`、`XiaomiMIMOBot`、`OllamaBot`、
`CustomBot` 和 `BaseOpenAIBot` 导入路径仍保留，对应类只提供轻量构造入口。
请将 `capabilities=` 和旧的 `*Config` 配置组替换为 `ModelProfile`、
`CustomProfile` 和 `InvocationPolicy`。服务商类不再承载模型能力的默认配置。
`get_custom_provider_meta` 已移至 `apix.agent.store.utils.llm_provider_helper`；
旧导入路径仍保留以便迁移，Bot 构造过程不会查询存储。

在 `source` 目录下运行离线契约测试：

```shell
uv run pytest tests/agent/sdk -q
```

真实服务商测试需要显式启用，并会产生付费推理调用。
设置 `APIX_LIVE_PROVIDER`、`APIX_LIVE_MODEL` 和 `APIX_LIVE_API_KEY`，
必要时再设置 `APIX_LIVE_ENDPOINT`，然后运行
`uv run pytest tests/integration/test_llm_provider_live.py -q`。
这些测试覆盖聊天、用量统计、流式输出、由 Apix 执行函数工具及多轮推理历史回传，
不会使用服务商原生工具。缺少凭证时会跳过测试；仅通过预置响应数据测试，
不足以将服务商标记为 `verified`。

协议参考：[OpenAI Responses 流式事件](https://developers.openai.com/api/reference/resources/responses/streaming-events)、
[OpenAI 无状态推理](https://developers.openai.com/api/docs/guides/reasoning)、
[Anthropic 流式响应](https://platform.claude.com/docs/en/build-with-claude/streaming)、
[Gemini 思考签名](https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures)。
