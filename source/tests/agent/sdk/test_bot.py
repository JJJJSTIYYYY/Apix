from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from apix.agent.sdk.bot import (
    BaseBot,
    BaseOpenAIBot,
    DeepSeekBot,
    MessageConfig,
    MiniMaxBot,
    ModelCapabilities,
    OllamaBot,
    OpenAIBot,
    ReasoningConfig,
    RequestConfig,
    XiaomiMIMOBot,
)
from apix.agent.sdk.bot.base_bot import _model_dump, _read
from apix.agent.sdk.tool import ToolNode, tool
from apix.agent.sdk.utils.message import (
    ApixAiMessage,
    ApixAiMessageAccumulator,
    ApixAiMessageChunk,
    ApixDeveloperMessage,
    ApixSystemMessage,
    ApixToolMessage,
    ApixUserMessage,
)


class FakeCreate:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        return response() if callable(response) else response


class FakeChatClient:
    def __init__(self, *responses):
        self.create = FakeCreate(*responses)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create.create)
        )


class FakeResponsesClient:
    def __init__(self, *responses):
        self.create = FakeCreate(*responses)
        self.responses = SimpleNamespace(create=self.create.create)


class FakeOllamaClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        return response() if callable(response) else response


def async_stream(*items):
    async def generate():
        for item in items:
            yield item

    return generate()


@tool
def weather(city: str) -> str:
    """Get the current weather."""
    return city


def chat_response(*, content="answer", reasoning=None, tool_calls=None):
    message = {
        "content": content,
        "tool_calls": tool_calls,
    }
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return {
        "id": "chat-1",
        "model": "provider-model",
        "choices": [
            {
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3},
    }


def test_capability_defaults_are_isolated_and_hierarchy_is_correct():
    first = ModelCapabilities()
    second = ModelCapabilities()

    assert first.message_config.supported_roles == ()
    assert second.message_config.supported_roles == ()
    assert first.request_config is not second.request_config
    assert first.message_config is not second.message_config
    assert first.reasoning_config is not second.reasoning_config
    assert first.tool_config is not second.tool_config
    assert first.stream_config is not second.stream_config
    assert issubclass(BaseOpenAIBot, BaseBot)
    assert issubclass(OpenAIBot, BaseOpenAIBot)
    assert issubclass(DeepSeekBot, BaseOpenAIBot)
    assert issubclass(MiniMaxBot, BaseOpenAIBot)
    assert issubclass(XiaomiMIMOBot, BaseOpenAIBot)
    assert issubclass(OllamaBot, BaseBot)


def test_sdk_object_helpers_support_mappings_attributes_and_dump_protocols():
    class ModelValue:
        def model_dump(self, **kwargs):
            assert kwargs == {"exclude_none": True}
            return {"model": 1}

    class DictValue:
        def to_dict(self):
            return {"dict": 2}

    class PlainValue:
        def __init__(self):
            self.visible = [1, {"nested": True}]
            self.none = None
            self._private = "hidden"

    marker = object()
    assert _read({"key": "mapping"}, "key") == "mapping"
    assert _read(SimpleNamespace(key="attribute"), "key") == "attribute"
    assert _model_dump(ModelValue()) == {"model": 1}
    assert _model_dump(DictValue()) == {"dict": 2}
    assert _model_dump(PlainValue()) == {
        "visible": [1, {"nested": True}]
    }
    assert _model_dump((1, 2)) == [1, 2]
    assert _model_dump(marker) is marker


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"model": ""}, ValueError),
        ({"model": "m", "role_schema": "assistant"}, TypeError),
        (
            {
                "model": "m",
                "role_schema": {
                    "name": "",
                    "title": None,
                    "definition": "Be helpful.",
                },
            },
            TypeError,
        ),
        ({"model": "m", "endpoint": ""}, ValueError),
        ({"model": "m", "api_key": None}, TypeError),
    ],
)
def test_base_constructor_validates_required_properties(kwargs, error):
    defaults = {
        "model": "m",
        "role_schema": None,
        "endpoint": "http://localhost:11434",
        "api_key": "",
        "client": object(),
    }
    defaults.update(kwargs)
    with pytest.raises(error):
        OllamaBot(**defaults)


def test_bind_role_schema_binds_copies_and_replaces_role():
    bot = DeepSeekBot(
        model="deepseek-chat",
        api_key="key",
        client=object(),
    )
    role_schema = {
        "name": " Alice ",
        "title": "Assistant",
        "definition": "Be concise.",
    }

    assert hasattr(bot, "name")
    assert bot.role_schema is None
    assert bot.bind_role_schema(role_schema) is bot
    assert hasattr(bot, "name")
    assert bot.role_schema == role_schema
    assert [
        message.content
        for message in bot._ordered_messages(
            [ApixUserMessage(content="question")],
            [ApixSystemMessage(content="global")],
        )
    ] == [
        "global",
        (
            "## Role Definition\n\n"
            "- Your name: Alice.\n"
            "- Your title: Assistant.\n"
            "- Your Characteristics:\n"
            "  Be concise.\n"
        ),
        "question",
    ]

    role_schema["name"] = "Changed externally"
    assert bot.role_schema["name"] == " Alice "

    replacement = {
        "name": "Bob",
        "title": None,
        "definition": "Be thorough.",
    }
    bot.bind_role_schema(replacement)
    assert bot.role_schema == replacement


@pytest.mark.parametrize(
    "role_schema",
    [
        None,
        "assistant",
        {},
        {"name": "Alice"},
        {"name": 1, "definition": "Be helpful."},
        {"name": "Alice", "definition": None},
        {
            "name": "Alice",
            "title": 1,
            "definition": "Be helpful.",
        },
    ],
)
def test_bind_role_schema_rejects_invalid_values(role_schema):
    bot = DeepSeekBot(
        model="deepseek-chat",
        api_key="key",
        client=object(),
    )

    with pytest.raises(TypeError, match="RoleSchema"):
        bot.bind_role_schema(role_schema)


def test_explicit_api_key_is_required_for_openai_compatible_bots():
    with pytest.raises(ValueError, match="supplied explicitly"):
        DeepSeekBot(model="deepseek-chat", api_key="", client=object())


def test_bind_tools_replaces_and_copies_schemas():
    client = FakeChatClient(chat_response())
    bot = DeepSeekBot(
        model="deepseek-v4-flash",
        api_key="key",
        client=client,
    )

    assert bot.bind_tools([weather]) is bot
    schema = bot.tool_schemas
    schema[0]["function"]["name"] = "changed"
    assert bot.tool_schemas[0]["function"]["name"] == "weather"

    bot.bind_tools(ToolNode(weather))
    assert len(bot.tool_schemas) == 1
    bot.bind_tools([])
    assert bot.tool_schemas == []

    with pytest.raises(TypeError, match="only Tool"):
        bot.bind_tools([object()])
    with pytest.raises(TypeError, match="iterable"):
        bot.bind_tools("weather")
    with pytest.raises(TypeError, match="iterable"):
        bot.bind_tools(123)

    with pytest.raises(TypeError, match="messages must be a list"):
        bot._ordered_messages((), None)
    with pytest.raises(TypeError, match="system_prompt"):
        bot._ordered_messages([], ())


def test_chat_serialization_and_argument_validation_edge_cases():
    capabilities = ModelCapabilities(
        message_config=MessageConfig(
            supported_roles=("user", "ai", "tool"),
            include_name=True,
        ),
        reasoning_config=ReasoningConfig(
            supported_efforts=("low",),
            effort_map={"low": "low", "medium": "low", "high": "high"},
        ),
    )
    bot = DeepSeekBot(
        model="deepseek",
        api_key="key",
        capabilities=capabilities,
        client=FakeChatClient(chat_response()),
    )

    assert bot.convert_message_for_api(ApixSystemMessage(content="drop")) is None
    assert bot.convert_message_for_api(
        ApixUserMessage(content="hi", name="user-name")
    )["name"] == "user-name"
    assert bot.convert_message_for_api(
        ApixToolMessage(content=None, tool_call_id="call", name="tool")
    ) == {
        "role": "tool",
        "content": "",
        "name": "tool",
        "tool_call_id": "call",
    }
    with pytest.raises(TypeError, match="complete ApixMessageBase"):
        bot.convert_message_for_api(object())

    assert bot._parse_tool_arguments(None) is None
    assert bot._parse_tool_arguments({"a": 1}) == {"a": 1}
    with pytest.raises(TypeError, match="JSON object"):
        bot._parse_tool_arguments(1)
    with pytest.raises(ValueError, match="invalid JSON"):
        bot._parse_tool_arguments("{")
    with pytest.raises(ValueError, match="decode to a JSON object"):
        bot._parse_tool_arguments("[]")
    with pytest.raises(ValueError, match="function name"):
        bot._chat_tool_calls([{"id": "call", "function": {}}])
    with pytest.raises(ValueError, match="contains no choices"):
        bot.convert_message_to_apix({"choices": []})

    assert bot._normalize_finish_reason(None) is None
    assert bot._normalize_finish_reason("max_tokens") == "length"
    assert bot._normalize_finish_reason("unexpected") == "unknown"
    with pytest.raises(ValueError, match="does not support"):
        bot._reasoning_request(True, "high")


@pytest.mark.asyncio
async def test_deepseek_invoke_orders_prompts_filters_roles_and_round_trips_reasoning():
    tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "weather",
                "arguments": '{"city":"Tokyo"}',
            },
        }
    ]
    client = FakeChatClient(
        chat_response(content="", reasoning="think", tool_calls=tool_calls)
    )
    bot = DeepSeekBot(
        model="deepseek-v4-flash",
        api_key="key",
        role_schema={
            "name": "Alice",
            "title": None,
            "definition": "You are Alice.",
        },
        client=client,
    ).bind_tools([weather])

    result = await bot.invoke(
        [
            ApixDeveloperMessage(content="filtered"),
            ApixUserMessage(content="weather?"),
        ],
        system_prompt=[ApixSystemMessage(content="global")],
        reasoning_effort="medium",
    )

    request = client.create.calls[0]
    assert [item["content"] for item in request["messages"]] == [
        "global",
        (
            "## Role Definition\n\n"
            "- Your name: Alice.\n"
            "- Your Characteristics:\n"
            "  You are Alice.\n"
        ),
        "weather?",
    ]
    assert request["reasoning_effort"] == "high"
    assert request["extra_body"]["thinking"] == {"type": "enabled"}
    assert request["tools"][0]["function"]["name"] == "weather"

    assert result.name == "Alice"
    assert result.reasoning == "think"
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls == [
        {
            "call_id": "call-1",
            "tool_name": "weather",
            "args": {"city": "Tokyo"},
        }
    ]
    assert result.metadata["provider"] == "deepseek"
    assert result.metadata["usage"]["prompt_tokens"] == 2

    serialized = bot.convert_message_for_api(result)
    assert serialized["content"] == ""
    assert serialized["reasoning_content"] == "think"
    assert serialized["tool_calls"][0]["id"] == "call-1"


@pytest.mark.asyncio
async def test_chat_compatible_stream_converts_all_delta_types():
    client = FakeChatClient(
        lambda: async_stream(
            {
                "id": "chat-2",
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "delta": {
                            "reasoning_content": "why ",
                            "content": "hello ",
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chat-2",
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "delta": {
                            "content": "world",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-2",
                                    "function": {
                                        "name": "weather",
                                        "arguments": '{"city":"Tokyo"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            },
            {
                "id": "chat-2",
                "model": "deepseek-v4-flash",
                "choices": [],
                "usage": {"total_tokens": 9},
            },
        )
    )
    bot = DeepSeekBot(
        model="deepseek-v4-flash",
        api_key="key",
        client=client,
    )

    chunks = [chunk async for chunk in bot.stream([ApixUserMessage(content="hi")])]
    assert len({chunk.message_uid for chunk in chunks}) == 1
    assert chunks[0].reasoning_delta == "why "
    assert chunks[1].finish_reason == "tool_calls"
    assert chunks[2].metadata["usage"] == {"total_tokens": 9}

    accumulator = ApixAiMessageAccumulator()
    for chunk in chunks:
        accumulator.add(chunk)
    message = accumulator.to_message(require_finished=True)
    assert message.content == "hello world"
    assert message.reasoning == "why "
    assert message.tool_calls[0]["args"] == {"city": "Tokyo"}


@pytest.mark.parametrize(
    ("bot_class", "expected_enabled", "expected_disabled"),
    [
        (MiniMaxBot, "adaptive", "disabled"),
        (XiaomiMIMOBot, "enabled", "disabled"),
    ],
)
def test_provider_specific_thinking_fields(
    bot_class,
    expected_enabled,
    expected_disabled,
):
    bot = bot_class(
        model="provider-model",
        api_key="key",
        client=FakeChatClient(chat_response()),
    )
    enabled = bot._chat_request(
        [ApixUserMessage(content="hi")],
        None,
        reasoning=True,
        reasoning_effort="high",
        extra_body={},
        stream=False,
    )
    disabled = bot._chat_request(
        [ApixUserMessage(content="hi")],
        None,
        reasoning=False,
        reasoning_effort="high",
        extra_body={},
        stream=False,
    )

    assert "reasoning_effort" not in enabled
    assert enabled["extra_body"]["thinking"]["type"] == expected_enabled
    assert disabled["extra_body"]["thinking"]["type"] == expected_disabled
    if bot_class is MiniMaxBot:
        assert enabled["extra_body"]["reasoning_split"] is True


def test_minimax_reasoning_details_are_preserved_for_tool_round_trip():
    bot = MiniMaxBot(
        model="MiniMax-M3",
        api_key="key",
        client=FakeChatClient(chat_response()),
    )
    response = chat_response(
        content="",
        tool_calls=[
            {
                "id": "call-mm",
                "function": {"name": "weather", "arguments": "{}"},
            }
        ],
    )
    response["choices"][0]["message"]["reasoning_details"] = [
        {"type": "reasoning.text", "text": "thinking"}
    ]

    message = bot.convert_message_to_apix(response)
    assert message.reasoning == "thinking"
    assert message.extensions["reasoning_details"][0]["text"] == "thinking"
    serialized = bot.convert_message_for_api(message)
    assert serialized["reasoning_details"][0]["text"] == "thinking"


@pytest.mark.asyncio
async def test_openai_responses_invoke_preserves_output_items_and_tools():
    output = [
        {
            "id": "reason-1",
            "type": "reasoning",
            "summary": [{"type": "summary_text", "text": "summary"}],
            "encrypted_content": "opaque",
        },
        {
            "id": "fc-1",
            "type": "function_call",
            "call_id": "call-openai",
            "name": "weather",
            "arguments": '{"city":"Tokyo"}',
        },
    ]
    response = {
        "id": "resp-openai",
        "model": "gpt-test",
        "status": "completed",
        "output": output,
        "usage": {"input_tokens": 4, "output_tokens": 5},
    }
    client = FakeResponsesClient(response)
    bot = OpenAIBot(
        model="gpt-test",
        api_key="key",
        role_schema={
            "name": "Alice",
            "title": None,
            "definition": "Be Alice.",
        },
        client=client,
    ).bind_tools([weather])

    result = await bot.invoke(
        [ApixUserMessage(content="weather")],
        system_prompt=[ApixSystemMessage(content="global")],
        reasoning=False,
    )

    request = client.create.calls[0]
    assert request["reasoning"] == {"effort": "none"}
    assert request["store"] is False
    assert "include" not in request
    assert [item["content"] for item in request["input"]] == [
        "global",
        (
            "## Role Definition\n\n"
            "- Your name: Alice.\n"
            "- Your Characteristics:\n"
            "  Be Alice.\n"
        ),
        "weather",
    ]
    assert request["tools"][0] == {
        "type": "function",
        "name": "weather",
        "description": "Get the current weather.",
        "parameters": weather.schema["function"]["parameters"],
    }

    assert result.reasoning == "summary"
    assert result.tool_calls[0]["call_id"] == "call-openai"
    assert result.extensions["response_output"][0]["encrypted_content"] == "opaque"
    assert bot.convert_message_for_api(result) == output
    assert bot.convert_message_for_api(
        ApixToolMessage(
            content="sunny",
            name="weather",
            tool_call_id="call-openai",
        )
    ) == {
        "type": "function_call_output",
        "call_id": "call-openai",
        "output": "sunny",
    }


@pytest.mark.asyncio
async def test_openai_responses_stream_builds_tool_call_and_final_state():
    completed = {
        "id": "resp-stream",
        "model": "gpt-test",
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "call_id": "call-stream",
                "name": "weather",
                "arguments": '{"city":"Tokyo"}',
            }
        ],
        "usage": {"total_tokens": 8},
    }
    client = FakeResponsesClient(
        lambda: async_stream(
            {"type": "response.output_text.delta", "delta": "checking"},
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "type": "function_call",
                    "call_id": "call-stream",
                    "name": "weather",
                    "arguments": "",
                },
            },
            {
                "type": "response.function_call_arguments.delta",
                "output_index": 0,
                "delta": '{"city":"Tokyo"}',
            },
            {"type": "response.completed", "response": completed},
        )
    )
    bot = OpenAIBot(model="gpt-test", api_key="key", client=client)

    chunks = [chunk async for chunk in bot.stream([ApixUserMessage(content="hi")])]
    accumulator = ApixAiMessageAccumulator()
    for chunk in chunks:
        accumulator.add(chunk)
    message = accumulator.to_message(require_finished=True)

    assert message.content == "checking"
    assert message.finish_reason == "tool_calls"
    assert message.tool_calls[0] == {
        "call_id": "call-stream",
        "tool_name": "weather",
        "args": {"city": "Tokyo"},
    }
    assert message.metadata["usage"] == {"total_tokens": 8}
    assert message.extensions["response_output"][0]["type"] == "function_call"


def test_openai_responses_manual_serialization_multimodal_and_no_reasoning_model():
    capabilities = replace(
        OpenAIBot.capabilities,
        message_config=replace(
            OpenAIBot.capabilities.message_config,
            supported_roles=("user", "ai", "tool"),
        ),
        reasoning_config=replace(
            OpenAIBot.capabilities.reasoning_config,
            supported=False,
        ),
    )
    bot = OpenAIBot(
        model="non-reasoning",
        api_key="key",
        capabilities=capabilities,
        client=FakeResponsesClient({}),
    ).bind_tools([weather])

    user = bot.convert_message_for_api(
        ApixUserMessage(
            content=[
                {"type": "text", "text": "look"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.test/image.png"},
                },
                {"type": "input_text", "text": "already converted"},
            ]
        )
    )
    assert user["content"] == [
        {"type": "input_text", "text": "look"},
        {
            "type": "input_image",
            "image_url": "https://example.test/image.png",
        },
        {"type": "input_text", "text": "already converted"},
    ]
    assert bot.convert_message_for_api(ApixSystemMessage(content="drop")) is None
    with pytest.raises(TypeError, match="complete ApixMessageBase"):
        bot.convert_message_for_api(object())

    ai_items = bot.convert_message_for_api(
        ApixAiMessage(
            content="working",
            tool_calls=[
                {
                    "call_id": "call-manual",
                    "tool_name": "weather",
                    "args": {"city": "Tokyo"},
                }
            ],
        )
    )
    assert [item.get("type") for item in ai_items] == [None, "function_call"]
    request = bot._responses_request(
        [ApixUserMessage(content="hi")],
        None,
        reasoning=True,
        reasoning_effort="high",
        extra_body={"temperature": 0},
        stream=False,
    )
    assert "reasoning" not in request
    assert "include" not in request
    assert request["extra_body"] == {"temperature": 0}


def test_openai_response_refusal_incomplete_and_stream_event_variants():
    bot = OpenAIBot(
        model="gpt-test",
        api_key="key",
        client=FakeResponsesClient({}),
    )
    incomplete = {
        "id": "resp-incomplete",
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "partial"},
                    {"type": "refusal", "refusal": "cannot continue"},
                ],
            }
        ],
    }
    message = bot.convert_message_to_apix(incomplete)
    assert message.content == "partial"
    assert message.refusal == "cannot continue"
    assert message.finish_reason == "length"

    reasoning = bot.convert_message_to_apix(
        {
            "type": "response.reasoning_summary_text.delta",
            "delta": "summary",
            "response_id": "resp-stream",
        },
        stream=True,
    )
    refusal = bot.convert_message_to_apix(
        {"type": "response.refusal.delta", "delta": "no"},
        stream=True,
    )
    mapping_args = bot.convert_message_to_apix(
        {
            "type": "response.output_item.added",
            "output_index": 1,
            "item": {
                "type": "function_call",
                "call_id": "call",
                "name": "weather",
                "arguments": {"city": "Tokyo"},
            },
        },
        stream=True,
    )
    failed = bot.convert_message_to_apix(
        {"type": "response.failed", "status": "failed"},
        stream=True,
    )
    assert reasoning.reasoning_delta == "summary"
    assert reasoning.metadata["id"] == "resp-stream"
    assert refusal.refusal_delta == "no"
    assert mapping_args.tool_call_deltas[0].index == 1
    assert mapping_args.tool_call_deltas[0].arguments_delta == '{"city":"Tokyo"}'
    assert failed.finish_reason == "unknown"


@pytest.mark.asyncio
async def test_ollama_native_protocol_invoke_and_stream():
    invoke_response = {
        "model": "qwen3",
        "message": {
            "role": "assistant",
            "content": "",
            "thinking": "considering",
            "tool_calls": [
                {
                    "function": {
                        "name": "weather",
                        "arguments": {"city": "Tokyo"},
                    }
                }
            ],
        },
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 2,
        "eval_count": 3,
        "total_duration": 2_000_000_000,
    }
    client = FakeOllamaClient(
        invoke_response,
        lambda: async_stream(
            {
                "model": "qwen3",
                "message": {"thinking": "why ", "content": ""},
                "done": False,
            },
            {
                "model": "qwen3",
                "message": {
                    "content": "checking",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "weather",
                                "arguments": {"city": "Tokyo"},
                            }
                        }
                    ],
                },
                "done": False,
            },
            {
                "model": "qwen3",
                "message": {"content": ""},
                "done": True,
                "done_reason": "stop",
            },
        ),
    )
    bot = OllamaBot(
        model="qwen3",
        role_schema={
            "name": "Alice",
            "title": None,
            "definition": "Be Alice.",
        },
        client=client,
    ).bind_tools([weather])

    result = await bot.invoke(
        [ApixUserMessage(content="weather")],
        system_prompt=[ApixSystemMessage(content="global")],
        reasoning=False,
    )
    request = client.calls[0]
    assert [message["content"] for message in request["messages"]] == [
        "global",
        (
            "## Role Definition\n\n"
            "- Your name: Alice.\n"
            "- Your Characteristics:\n"
            "  Be Alice.\n"
        ),
        "weather",
    ]
    assert request["think"] is False
    assert result.reasoning == "considering"
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls[0]["args"] == {"city": "Tokyo"}
    assert result.metadata["usage"]["total_tokens"] == 5
    assert result.metadata["provider_duration"] == 2.0

    chunks = [
        chunk
        async for chunk in bot.stream(
            [ApixUserMessage(content="weather")],
            reasoning_effort="low",
        )
    ]
    assert client.calls[1]["think"] == "low"
    assert chunks[-1].finish_reason == "tool_calls"

    accumulator = ApixAiMessageAccumulator()
    for chunk in chunks:
        accumulator.add(chunk)
    streamed = accumulator.to_message(require_finished=True)
    assert streamed.reasoning == "why "
    assert streamed.content == "checking"
    assert streamed.tool_calls[0]["tool_name"] == "weather"

    serialized = bot.convert_message_for_api(result)
    assert serialized["thinking"] == "considering"
    assert serialized["tool_calls"][0]["function"]["arguments"] == {
        "city": "Tokyo"
    }


def test_ollama_constructor_auth_and_tool_message_serialization(monkeypatch):
    import ollama

    captured = {}
    fake_client = FakeOllamaClient({})

    def client_factory(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(ollama, "AsyncClient", client_factory)
    bot = OllamaBot(
        model="qwen3",
        endpoint="https://ollama.example.test/",
        api_key="secret",
    )
    assert bot.endpoint == "https://ollama.example.test"
    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert bot.convert_message_for_api(
        ApixToolMessage(
            content="result",
            name="weather",
            tool_call_id="call",
        )
    ) == {
        "role": "tool",
        "content": "result",
        "tool_name": "weather",
    }
    with pytest.raises(TypeError, match="complete ApixMessageBase"):
        bot.convert_message_for_api(object())
    with pytest.raises(ValueError, match="function name"):
        bot._ollama_tool_calls([{"function": {}}])


def test_provider_classes_only_declare_provider_endpoint_and_capabilities():
    for bot_class in (OpenAIBot, DeepSeekBot, MiniMaxBot, XiaomiMIMOBot):
        public_members = {
            name
            for name in bot_class.__dict__
            if not name.startswith("_")
        }
        assert public_members == {
            "provider",
            "default_endpoint",
            "capabilities",
        }

    assert OpenAIBot.capabilities.request_config.api_style == "responses"
    assert (
        DeepSeekBot.capabilities.reasoning_config.history_field_map[
            "reasoning_content"
        ]
        == ("reasoning",)
    )
    assert (
        MiniMaxBot.capabilities.reasoning_config.stream_delta_mode
        == "cumulative"
    )
    assert XiaomiMIMOBot.capabilities.reasoning_config.effort_path is None


def test_constructor_capability_and_endpoint_validation():
    with pytest.raises(TypeError, match="ModelCapabilities"):
        OllamaBot(
            model="qwen3",
            client=object(),
            capabilities=object(),
        )

    with pytest.raises(ValueError, match="endpoint must be supplied"):
        BaseOpenAIBot(model="model", api_key="key", client=object())


def test_openai_compatible_client_factory_uses_runtime_configuration(
    monkeypatch,
):
    import openai

    captured = {}
    fake_client = FakeChatClient(chat_response())

    def client_factory(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(openai, "AsyncOpenAI", client_factory)
    bot = DeepSeekBot(
        model="deepseek-v4-flash",
        api_key="secret",
        endpoint="https://deepseek.example.test/",
    )

    assert bot.endpoint == "https://deepseek.example.test"
    assert captured["api_key"] == "secret"
    assert captured["base_url"] == bot.endpoint
    assert captured["max_retries"] > 0
    assert captured["timeout"] > 0


def test_capabilities_drive_reasoning_summary_extra_body_and_tools():
    capabilities = replace(
        OpenAIBot.capabilities,
        request_config=RequestConfig(
            api_style="responses",
            request_defaults={"store": False},
            extra_body_defaults={
                "default": 1,
                "overridden": "default",
            },
        ),
        reasoning_config=replace(
            OpenAIBot.capabilities.reasoning_config,
            request_defaults={"reasoning": {"summary": "auto"}},
            enabled_extra_body={"thinking": {"type": "enabled"}},
        ),
    )
    bot = OpenAIBot(
        model="gpt-test",
        api_key="key",
        capabilities=capabilities,
        client=FakeResponsesClient({}),
    )
    bot._tool_schemas = [
        {},
        {"function": "invalid"},
        {
            "function": {
                "name": "strict_tool",
                "description": "Strict tool",
                "parameters": {"type": "object"},
                "strict": True,
            }
        },
    ]

    request = bot._responses_request(
        [ApixUserMessage(content="hi")],
        None,
        reasoning=True,
        reasoning_effort="medium",
        extra_body={
            "overridden": "caller",
            "thinking": {"budget": 128},
            "custom": 2,
        },
        stream=False,
    )

    assert request["reasoning"] == {"effort": "medium", "summary": "auto"}
    assert request["extra_body"] == {
        "default": 1,
        "overridden": "caller",
        "thinking": {"type": "enabled", "budget": 128},
        "custom": 2,
    }
    assert request["tools"] == [
        {
            "type": "function",
            "name": "strict_tool",
            "description": "Strict tool",
            "parameters": {"type": "object"},
            "strict": True,
        }
    ]

    with pytest.raises(TypeError, match="extra_body"):
        bot._provider_extra_body([], reasoning=True)


def test_response_and_chat_serialization_cover_composite_inputs():
    openai_bot = OpenAIBot(
        model="gpt-test",
        api_key="key",
        client=FakeResponsesClient({}),
    )
    prepared = openai_bot._prepare_api_messages(
        [
            ApixAiMessage(
                tool_calls=[
                    {
                        "call_id": "call",
                        "tool_name": "weather",
                        "args": {"city": "Tokyo"},
                    }
                ]
            )
        ],
        None,
    )
    assert prepared[0]["type"] == "function_call"

    minimax_bot = MiniMaxBot(
        model="minimax-test",
        api_key="key",
        client=FakeChatClient(chat_response()),
    )
    serialized = minimax_bot.convert_message_for_api(
        ApixAiMessage(content="answer", reasoning="thinking")
    )
    assert serialized["reasoning_content"] == "thinking"
    assert "reasoning_details" not in serialized

    content = openai_bot._responses_content(
        [
            "ignored",
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": "image-data"},
        ]
    )
    assert content == [
        {"type": "input_text", "text": "hello"},
        {"type": "input_image", "image_url": "image-data"},
    ]

    deltas = DeepSeekBot._chat_tool_call_deltas(
        [
            {
                "function": {
                    "name": "weather",
                    "arguments": {"city": "Tokyo"},
                }
            }
        ]
    )
    assert deltas[0].arguments_delta == '{"city":"Tokyo"}'


def test_response_validation_and_completed_finish_reason():
    bot = OpenAIBot(
        model="gpt-test",
        api_key="key",
        client=FakeResponsesClient({}),
    )
    with pytest.raises(ValueError, match="call_id/name"):
        bot._response_tool_calls(
            [{"type": "function_call", "name": "weather"}]
        )
    assert bot._response_finish_reason(
        {"status": "completed", "output": []}
    ) == "stop"


@pytest.mark.asyncio
async def test_base_stream_contract_raises_when_called_directly():
    bot = DeepSeekBot(
        model="deepseek-v4-flash",
        api_key="key",
        client=FakeChatClient(chat_response()),
    )
    with pytest.raises(NotImplementedError):
        await BaseBot.stream(bot, [])


@pytest.mark.asyncio
async def test_minimax_stream_normalizes_cumulative_reasoning_details():
    client = FakeChatClient(
        lambda: async_stream(
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_details": [{"text": "think"}]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_details": [{"text": "thinking"}]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_details": [{"text": " independently"}]
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )
    )
    bot = MiniMaxBot(model="MiniMax-M3", api_key="key", client=client)

    chunks = [
        chunk
        async for chunk in bot.stream([ApixUserMessage(content="hi")])
    ]
    assert [chunk.reasoning_delta for chunk in chunks] == [
        "think",
        "ing",
        " independently",
    ]


@pytest.mark.asyncio
async def test_openai_compatible_invoke_and_stream_reject_wrong_conversion(
    monkeypatch,
):
    invoke_bot = DeepSeekBot(
        model="deepseek-v4-flash",
        api_key="key",
        client=FakeChatClient(chat_response()),
    )
    monkeypatch.setattr(
        invoke_bot,
        "convert_message_to_apix",
        lambda *args, **kwargs: ApixAiMessageChunk(),
    )
    with pytest.raises(TypeError, match="streaming chunk"):
        await invoke_bot.invoke([ApixUserMessage(content="hi")])

    stream_bot = DeepSeekBot(
        model="deepseek-v4-flash",
        api_key="key",
        client=FakeChatClient(lambda: async_stream(chat_response())),
    )
    monkeypatch.setattr(
        stream_bot,
        "convert_message_to_apix",
        lambda *args, **kwargs: ApixAiMessage(),
    )
    with pytest.raises(TypeError, match="complete message"):
        async for _ in stream_bot.stream([ApixUserMessage(content="hi")]):
            pass


def test_ollama_capability_validation_and_role_filtering():
    bot = OllamaBot(model="qwen3", client=FakeOllamaClient({}))
    assert bot.convert_message_for_api(
        ApixDeveloperMessage(content="unsupported")
    ) is None
    with pytest.raises(TypeError, match="extra_body"):
        bot._ollama_request(
            [ApixUserMessage(content="hi")],
            None,
            reasoning=True,
            reasoning_effort="high",
            extra_body=[],
            stream=False,
        )

    unsupported = replace(
        OllamaBot.capabilities,
        reasoning_config=replace(
            OllamaBot.capabilities.reasoning_config,
            effort_map={
                "low": "xhigh",
                "medium": "medium",
                "high": "high",
            },
        ),
    )
    unsupported_bot = OllamaBot(
        model="qwen3",
        capabilities=unsupported,
        client=FakeOllamaClient({}),
    )
    with pytest.raises(ValueError, match="does not support"):
        unsupported_bot._ollama_request(
            [ApixUserMessage(content="hi")],
            None,
            reasoning=True,
            reasoning_effort="low",
            extra_body=None,
            stream=False,
        )


@pytest.mark.asyncio
async def test_ollama_invoke_and_stream_reject_wrong_conversion(monkeypatch):
    invoke_bot = OllamaBot(
        model="qwen3",
        client=FakeOllamaClient({"message": {}, "done": True}),
    )
    monkeypatch.setattr(
        invoke_bot,
        "convert_message_to_apix",
        lambda *args, **kwargs: ApixAiMessageChunk(),
    )
    with pytest.raises(TypeError, match="chunk"):
        await invoke_bot.invoke([ApixUserMessage(content="hi")])

    stream_bot = OllamaBot(
        model="qwen3",
        client=FakeOllamaClient(
            lambda: async_stream({"message": {}, "done": True})
        ),
    )
    monkeypatch.setattr(
        stream_bot,
        "convert_message_to_apix",
        lambda *args, **kwargs: ApixAiMessage(),
    )
    with pytest.raises(TypeError, match="message to stream"):
        async for _ in stream_bot.stream([ApixUserMessage(content="hi")]):
            pass
