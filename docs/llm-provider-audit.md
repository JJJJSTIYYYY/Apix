# Bot 官方文档核对记录

核对日期：2026-10-07。

本次覆盖全部 12 个内置 Provider，以及 `OpenAIBot`、`DeepSeekBot`、`XiaomiMIMOBot`、
`MiniMaxBot`、`OllamaBot`、`CustomBot`、`BaseOpenAIBot` 兼容入口。
兼容入口与统一 `Bot` 共用 Profile、Codec 和 Protocol，不维护另一套服务商逻辑。

核对对象是默认端点、请求协议、已配置模型的推理控制、函数工具选择、历史回传和流式字段。
这里只表示官方文档与离线契约对齐，不表示每个模型都做过真实调用。
所有 Provider 仍标记为 `community`，未使用 API Key，也未发起付费推理。

## 端点与协议

| Provider | 默认 Base URL | 协议 |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | 默认 Chat Completions；已配置推理型号使用 Responses |
| DeepSeek | `https://api.deepseek.com/v1` | Chat Completions |
| MiMo / xiaomimimo | `https://api.xiaomimimo.com/v1` | Chat Completions |
| MiniMax | `https://api.minimax.cn/v1` | Chat Completions，中国区 |
| Moonshot / Kimi | `https://api.moonshot.cn/v1` | Chat Completions |
| Z.AI | `https://api.z.ai/api/paas/v4` | Chat Completions |
| Qwen / 百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Chat Completions，中国内地默认地址 |
| Anthropic | `https://api.anthropic.com/v1` | Messages |
| Gemini | `https://generativelanguage.googleapis.com/v1beta` | GenerateContent |
| OpenRouter | `https://openrouter.ai/api/v1` | Chat Completions |
| SiliconFlow | `https://api.siliconflow.cn/v1` | Chat Completions |
| Ollama | `http://localhost:11434` | 原生 `/api/chat`，不是 `/v1/chat/completions` |

地域、账号产品与端点必须匹配。MiniMax 国际区应显式覆盖为 `https://api.minimax.io/v1`；
Z.AI Coding Plan、百炼国际区和业务空间地址也不能直接复用默认端点。
`CustomProfile(endpoint=...)` 只修改地址，不会自动转换 API 协议或模型能力。

## 逐项结论

### OpenAI

保留 Responses 无状态调用的 `store=False` 与加密推理内容回传。
补充 Pro 专用 Profile：`gpt-5-pro` 只接受 `high`；`gpt-5.2-pro` 接受
`medium/high/xhigh`，两者都不能关闭推理。普通 GPT-5.1/5.2 的匹配收窄为基础型号和日期快照，
不再把 Codex 等变体误认为拥有相同能力。GPT-5.1/5.2 Codex 与 o3-pro 仅保留已确认的 Responses
及无状态推理回传，不推断 effort 取值；需要显式强度时应提供专用 Profile。
o3/o4-mini 的基础能力也不再误匹配需要服务商原生工具的 Deep Research 变体。

来源：[GPT-5 Pro](https://developers.openai.com/api/docs/models/gpt-5-pro)、
[GPT-5.2 Pro](https://developers.openai.com/api/docs/models/gpt-5.2-pro)、
[GPT-5.2](https://developers.openai.com/api/docs/models/gpt-5.2)、
[推理与无状态回传](https://developers.openai.com/api/docs/guides/reasoning)、
[GPT-5.1 Codex Max](https://developers.openai.com/api/docs/models/gpt-5.1-codex-max)、
[GPT-5.2 Codex](https://developers.openai.com/api/docs/models/gpt-5.2-codex)、
[o3-pro](https://developers.openai.com/api/docs/models/o3-pro)、
[Deep Research 的原生工具要求](https://developers.openai.com/api/docs/guides/deep-research)。

### DeepSeek

补充当前 `deepseek-flash`，保留 V4 型号配置。推理使用 `thinking.type` 和
`reasoning_effort`；补齐官方强度别名以及 `none` 关闭推理的行为。
思考模式仅允许 `auto/none` 工具选择。修正历史回传：只要当前请求携带函数工具，
就保留全部历史 assistant 消息中的 `reasoning_content`，不再只保留带 `tool_calls` 的消息。

来源：[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)、
[Chat API](https://api-docs.deepseek.com/api/create-chat-completion/)、
[更新记录](https://api-docs.deepseek.com/updates/)。

### MiMo

推理 Profile 收窄为已核对的 `mimo-v2.5`、`mimo-v2.5-pro`，避免 `mimo-v2*` 命中 TTS 等变体。
使用 `thinking.type=enabled/disabled`；工具请求回传全部历史推理内容。
官方下线通知列出这两个型号将于 2026-10-21 下线，部署前应再次确认替代型号。
其他新型号可以走基础兼容请求，但其推理能力不再由旧系列通配符推断。

来源：[推理内容回传](https://mimo.mi.com/docs/en-US/usage-guide/passing-back-reasoning_content)、
[下线通知](https://mimo.mi.com/docs/zh-CN/updates/deprecate)。

### MiniMax

中国区默认地址改为当前官方文档使用的 `api.minimax.cn/v1`。
M2.x 不可关闭思考；M3 支持 `adaptive/disabled`；M3.1-Flash-Preview 始终思考，
并支持 `low/medium/high/xhigh/max`。默认发送 `reasoning_split=True`，
按当前 API 参考和 OpenAPI 使用增量 `reasoning_content`。

旧 M3 工具指南仍展示 `reasoning_details`，与当前接口参考存在差异。
因此保留 `providers.minimax.DETAILS_SCHEMA` 供旧端点或代理显式选择，
但不再将“累计 reasoning_details”作为 M3 的默认响应格式，也不按返回内容猜测格式。
国际站 M3.1 的可用范围另受 M Plan / MiniMax Code 限制，Profile 不代表账号已获访问权限。

来源：[中国区兼容指南](https://platform.minimaxi.com/docs/api-reference/text-openai-api)、
[当前 Chat API](https://platform.minimax.io/docs/api-reference/text-chat-openai)、
[官方 OpenAPI](https://platform.minimax.io/docs/api-reference/text/api/openapi-chat-openai.json)、
[旧 M3 工具指南](https://platform.minimax.io/docs/guides/text-m3-function-call)。

### Moonshot / Kimi

拆分基础 K2、K2 Thinking、K2.5/K2.6、K2.7-Code 和 K3。
基础 K2 不发送思考开关；Thinking 与 K2.7-Code 不允许关闭思考；K2.5/K2.6 使用显式开关。
K3 始终思考，支持 `low/high/max`，不发送 `thinking` 参数，并保留全部历史推理内容。
K3 允许 `required`，但思考模式不允许强制指定函数名。

来源：[思考模型](https://platform.kimi.com/docs/guide/use-thinking-models)、
[推理强度](https://platform.kimi.com/docs/guide/use-reasoning-effort)、
[工具选择](https://platform.kimi.com/docs/guide/use-tool-choice)、
[API 访问地址](https://platform.kimi.com/docs/get-api-key)。

### Z.AI

不再为所有 `glm-4*` 启用思考开关。区分 GLM-4.5/4.6/4.7、GLM-5/5.1/5.2 与 GLM-5.3。
5.2 支持关闭思考及官方 effort 别名；5.3 始终思考并支持 `low/high/max`。
按 API 参考将工具选择限制为 `auto`。
标准端点默认清理跨轮思考；若自定义 `thinking.clear_thinking=False`，
还需将 `replay` 改为 `always`，不能只修改请求字段。

来源：[思考模式](https://docs.z.ai/guides/capabilities/thinking-mode)、
[Chat API](https://docs.z.ai/api-reference/llm/chat-completion)。

### Qwen / 百炼

移除统一的 `qwen3*` 思考开关，拆分已确认的混合思考与 Thinking-only 型号。
Instruct/Coder 等未配置思考能力的变体不发送 `enable_thinking`。
旧版 Qwen3 混合思考型号在启用思考时只允许流式调用；关闭思考后可使用非流式。
非思考模式允许 `auto/none/指定函数名`，思考模式仅允许 `auto/none`，不承诺 `required`。
工具多轮请求不回传 `reasoning_content`。

来源：[深度思考](https://help.aliyun.com/zh/model-studio/deep-thinking/)、
[工具调用](https://help.aliyun.com/zh/model-studio/qwen-function-calling)、
[流式输出](https://help.aliyun.com/en/model-studio/stream)、
[模型更新记录](https://help.aliyun.com/zh/model-studio/newly-released-models)。

### Anthropic

已配置的 Claude 4.6/4.7/4.8 使用 `thinking.type=adaptive/disabled`，
补齐模型各自支持的 `output_config.effort`，并允许不启用思考时独立设置 effort。
保留原始 signed/redacted thinking blocks，不从显示文本重新构造签名块。
自适应思考不能套用旧版 extended thinking 的强制工具限制。
4.7/4.8 默认可能省略可见思考；需要摘要时，在启用思考的调用中设置
`request_options={"thinking": {"display": "summarized"}}`。

来源：[思考配置](https://platform.claude.com/docs/en/build-with-claude/thinking)、
[Effort](https://platform.claude.com/docs/en/build-with-claude/effort)、
[工具选择](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)。

### Gemini

只为明确的 GenerateContent 文本型号配置推理能力，不再匹配全部 `gemini-3*`。
3 Pro 接受 `low/high`，3.1 Pro 接受 `low/medium/high`，
3 Flash 和 3.1 Flash-Lite 接受 `minimal/low/medium/high`。
默认请求 `includeThoughts=True` 以接收思考摘要；显式 thinkingLevel 不能与 thinkingBudget 同用。
完整保留原始 parts、thoughtSignature 和模型返回的函数调用 ID。
`minimal` 不等于保证关闭思考；此处不混用 Interactions API 的参数。

来源：[Gemini 3 GenerateContent](https://ai.google.dev/gemini-api/docs/generate-content/gemini-3)、
[思考签名](https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures)。

### OpenRouter

修正其文本推理字段为 `reasoning`，并保留原始 `reasoning_details`。
流式 detail 按索引或 ID 聚合，拼接文本、摘要、签名及加密数据的片段，避免最后一个 chunk 覆盖此前内容。
历史回传保留这些原始块。
路由到不同模型后的 effort、开关和工具能力不是固定值，因此未为整个网关启用通用推理能力；
调用方应根据具体路由模型注册 Profile，不能直接套用 OpenAI 或 Anthropic 的原厂请求字段。

来源：[推理参数、推理块与回传](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)。

### SiliconFlow

补充官方列明的 `deepseek-ai/DeepSeek-V4-Flash`、`Pro/deepseek-ai/DeepSeek-V4`、
`Pro/zai-org/GLM-5.2`：使用 `enable_thinking`，effort 为 `high/max`。
`low/medium` 映射为 `high`，`xhigh` 映射为 `max`，不同于 DeepSeek 原厂的映射。
只承诺文档示例确认的自动函数工具选择；其他型号不继承这些能力。

来源：[Chat API](https://docs.siliconflow.cn/docs/api/chat-completions-post)。

### Ollama

确认使用原生 `/api/chat`、NDJSON、`message.thinking`、对象形式工具参数和 `tool_name`。
原生协议不编码 OpenAI 风格的强制工具选择或并行禁用开关。
收窄 Qwen3 和 GPT-OSS 匹配，避免误命中 Coder/Safeguard 等变体。
实际本地模型的 `think` 取值应以 `/api/show` 的 `thinking.values` 为准；
自定义模型和标签可能改变能力，需要专用 Profile，不会在 Bot 构造时隐式联网探测。

来源：[Chat API](https://docs.ollama.com/api/chat)、
[思考能力与发现](https://docs.ollama.com/capabilities/thinking)、
[工具调用](https://docs.ollama.com/capabilities/tool-calling)。

## 兼容与边界

未知模型只回退到基础协议格式，并不意味着已验证该模型可用或支持所有工具行为。
旧的 DeepSeek、MiMo、OpenAI 别名可能已经退役；保留构造或历史 Profile 不代表上游仍提供服务。
本文不承诺所有采样参数、图片/音频/视频输入、结构化输出和各地域产品均兼容。
MiniMax/MiMo 等未明确核实的强制工具选择组合仍需真实服务测试，不能据离线测试认定支持。

新增 `ModelProfile.request_options` 用于描述已确认的默认请求字段，例如 MiniMax 的 `reasoning_split`。
合并顺序为 Model Profile、InvocationPolicy、单次 request_options、extra_body；
上下文、工具、状态及推理控制字段仍不能通过原始选项绕过校验。

测试位于 `source/tests/agent/sdk/test_bot_official_contracts.py`，覆盖 12 个端点、
型号隔离、强度路径与映射、工具选择、请求默认值、历史回传和流式聚合。
另有原生签名块及传输协议测试。真实服务可用性、服务端新增限制和账号授权仍需带凭证联调确认。
