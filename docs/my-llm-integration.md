# 模型调用与消息存储

Apix 使用 `my-llm-py==1.0.1` 的 `MyLLM`、`ProviderProfile` 和 `ModelProfile`。
所有上游协议都显式使用 `stdio_protocol="openai_chat"`，消息和工具声明采用
[OpenAI Chat Completions 格式](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。
协议转换、SDK 客户端、流累积和终止校验由 my-llm-py 负责。

## 调用

```python
import os
from apix.agent.core.bot import ApixBot, ModelProfile, ProviderProfile
from apix.agent.core.utils.message import ApixAiMessage, ApixUserMessage
from apix.agent.core.tool import tool

@tool
def weather(city: str) -> str:
    """查询城市天气。"""
    return f"sunny in {city}"

bot = ApixBot(
    provider=ProviderProfile(
        protocol="openai_chat",  # 也支持 openai_responses / anthropic / gemini / ollama
        api_key=os.environ["MODEL_API_KEY"],
        # base_url="https://your-provider.example/v1",
    ),
    model=ModelProfile(model="your-model", supports_function_calling=True),
).bind_tools([weather])

async def ask():
    history = [ApixUserMessage(content="你好")]
    answer = await bot.invoke(history, max_tokens=1024)
    history.append(answer)
    return answer.content

async def ask_stream():
    stream = await bot.stream([{"role": "user", "content": "你好"}])
    async with stream:
        async for event in stream:
            for choice in event.get("choices", []):
                print(choice["delta"].get("content", ""), end="")
    # stream.result 是库累积完成的 Chat assistant 字典；无需另建累积器。
    return ApixAiMessage.from_chat(stream.result)
```

连接、重试、模型能力和厂商默认参数通过库的 profiles 配置。
`invoke` / `stream` 的其他关键字直接传给 `MyLLM.generate`，例如 `reasoning`、
`reasoning_effort`、`extra_body`。更换模型或 provider 时创建新 bot。
`tools=None` 使用绑定工具，`tools=[]` 在当前调用禁用工具。
`stream` 需先 await，再 `async with` 消费；取消或提前退出会由库关闭本次请求。
bot 本身不持有连接，无需 `aclose()`。

`tool_choice` 等厂商参数使用对应上游协议的 `extra_body` 或 profile 配置。
工具执行由 Apix 的 `ToolNode` 完成：

```python
from apix.agent.core.tool import ToolNode

async def tool_round():
    history = [ApixUserMessage(content="查询上海天气")]
    answer = await bot.invoke(history)
    history.append(answer)
    if answer.tool_calls:
        command = await ToolNode(weather).execute({"messages": history})
        history.extend(command.update["messages"])
        answer = await bot.invoke(history)
    return answer
```

当前 Ollama SDK 不能完整表达部分工具 JSON Schema 约束；my-llm-py 会抛出
`UnsupportedCapabilityError`。Apix 保留这个异常，不静默删除约束。
SDK 错误及库的 `StreamError`、`IncompleteStreamError` 等异常直接向调用者传播。
完成原因和 usage 位于 Chat 流事件中；需要存储时由调用方记录到 `metadata`。

## 消息

`ApixUserMessage`、`ApixSystemMessage`、`ApixDeveloperMessage`、`ApixAiMessage`、
`ApixToolMessage` 保留业务属性访问方式。`to_chat()` 返回发送给模型的字段，
`to_dict()` 还包含 `message_uid`、`metadata` 和 `extensions`，返回值均独立复制。
工具消息的 `name` 保留在应用/存储中，不作为 Chat tool 消息字段发送。

- `tool_calls`、`tool_call_id`、`refusal`、`audio`、`annotations`、`function_call` 为顶层协议字段。
- 工具调用为 `{"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}`；仅执行工具时解析 arguments。
- `reasoning_content` 是 Chat 兼容服务的顶层扩展，不属于官方 OpenAI 字段；回放由 profile 控制。
- `metadata` 保留 provider、model、usage、duration 等运行信息。
- `extensions` 保留文件、引用、任务、todo、搜索、系统指令及其他自定义业务字段。
- `content` 保留字符串、内容数组及 assistant 的 null；不将多模态内容转换为字符串。
- `info` 仍是仅用于数据库的业务事件，由上下文适配器读取，不能发送给模型。

## 数据库

SQLite 和 MySQL 的 messages 表同步增加协议列，并接受 `developer` 角色。
`content` 使用 JSON 编码存储，读取时恢复原值。SQLite 的 JSON 列为带校验的 TEXT，
MySQL 使用 JSON 列。初始化 SQL 将数据库默认排序规则统一为 `utf8mb4_unicode_ci`，
使存储过程参数与表字段保持一致。游标、消息标识、树分支、软删除和业务扩展保持原有语义。

本项目当前不需要保留旧数据，不提供旧消息结构的迁移或兼容路径。
新数据库由存储服务启动时执行对应的初始化 SQL；若已有空数据库采用旧表结构，
应重新建表后使用当前初始化 SQL。

在 macOS 上，从 Codex 运行临时 mysqld 时需在获得授权后使用沙箱外执行。
沙箱对 `hw.cachelinesize` 的读取限制可能导致 MySQL 在 `Aligned_atomic` 初始化时崩溃；
这不表示已有数据库损坏，也无需为此重装 MySQL。

真实 MySQL 9.5.0 已验证新库初始化、消息写入、工具回放和多模态内容读取。
可对隔离的、使用无密码 root 的临时测试实例运行集成测试；测试会创建并清理独立数据库：

```sh
APIX_TEST_MYSQL_SOCKET=/path/to/test/mysql.sock uv run pytest tests/agent/store/server/test_mysql_chat_live.py -q
```
