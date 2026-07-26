"""Tests for provider-backed chat model adapters."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import apix.agent.sdk.adapter.model.base as model_base
from apix.agent.sdk.adapter.model import (
    DeepSeekChatBot,
    DeepSeekProvider,
    MoonshotChatBot,
    MoonshotProvider,
    OllamaChatBot,
    OllamaProvider,
    OpenaiChatBot,
    OpenaiProvider,
)
from apix.agent.sdk.tool import ToolNode, tool
from apix.agent.sdk.utils.message import (
    ApixAiMessage,
    ApixAiMessageChunk,
    ApixDeveloperMessage,
    ApixSystemMessage,
    ApixToolMessage,
    ApixUserMessage,
)


class FakeAsyncStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for chunk in self._chunks:
            yield chunk


class FakeCompletions:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, *responses):
        self.completions = FakeCompletions(*responses)
        self.chat = SimpleNamespace(
            completions=self.completions,
        )


@tool(description="Look up the weather for one city.")
async def weather_lookup(city: str) -> str:
    return f"Weather for {city}"


@tool
async def current_time(timezone: str) -> str:
    """Return the current time for one timezone."""
    return timezone


def _tool_call(
    *,
    call_id="call-1",
    name="lookup",
    arguments='{"query":"Tokyo"}',
):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


def _completion(
    *,
    message=None,
    finish_reason="stop",
    choices=None,
    usage=None,
):
    if choices is None:
        choices = [
            SimpleNamespace(
                index=0,
                finish_reason=finish_reason,
                message=(
                    message
                    or SimpleNamespace(
                        content="answer",
                        refusal=None,
                        tool_calls=None,
                    )
                ),
            )
        ]

    return SimpleNamespace(
        id="completion-1",
        model="provider-model",
        created=1_700_000_000,
        choices=choices,
        usage=usage,
    )


def _chunk(
    *,
    delta=None,
    finish_reason=None,
    choices=None,
    usage=None,
):
    if choices is None:
        choices = [
            SimpleNamespace(
                index=0,
                finish_reason=finish_reason,
                delta=delta or SimpleNamespace(),
            )
        ]

    return SimpleNamespace(
        id="stream-1",
        model="provider-model",
        created=1_700_000_000,
        choices=choices,
        usage=usage,
    )


@pytest.mark.parametrize(
    ("provider_type", "chat_bot_type", "provider_name"),
    [
        (OpenaiProvider, OpenaiChatBot, "openai"),
        (DeepSeekProvider, DeepSeekChatBot, "deepseek"),
        (MoonshotProvider, MoonshotChatBot, "moonshot"),
        (OllamaProvider, OllamaChatBot, "ollama"),
    ],
)
def test_provider_get_chat_bot_returns_provider_specific_type(
    provider_type,
    chat_bot_type,
    provider_name,
):
    client = FakeClient()
    provider = provider_type(client=client)

    bot = provider.get_chat_bot(
        "model-name",
        name="researcher",
        role_definition="Act as a careful researcher.",
    )

    assert isinstance(bot, chat_bot_type)
    assert bot.client is client
    assert bot.provider == provider_name
    assert bot.model_name == "model-name"
    assert bot.name == "researcher"
    assert bot.role_definition == "Act as a careful researcher."


def test_provider_creates_async_openai_client(monkeypatch):
    captured = {}
    fake_client = object()

    def client_factory(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(model_base, "AsyncOpenAI", client_factory)

    provider = OpenaiProvider(
        api_key="secret",
        base_url="https://example.test/v1",
        max_retries=5,
        timeout=12,
    )

    assert provider.client is fake_client
    assert captured == {
        "api_key": "secret",
        "base_url": "https://example.test/v1",
        "max_retries": 5,
        "timeout": 12,
    }


def test_provider_reads_api_key_from_environment(monkeypatch):
    captured = {}
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-environment")
    monkeypatch.setattr(
        model_base,
        "AsyncOpenAI",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    provider = DeepSeekProvider()

    assert provider.api_key == "from-environment"
    assert captured["api_key"] == "from-environment"


def test_ollama_uses_local_openai_compatibility_defaults():
    provider = OllamaProvider(client=FakeClient())

    assert provider.api_key == "ollama"
    assert provider.base_url.endswith("/v1")


def test_provider_validation(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="API key is required"):
        OpenaiProvider()
    with pytest.raises(ValueError, match="max_retries"):
        OpenaiProvider(client=FakeClient(), max_retries=-1)

    provider = OpenaiProvider(client=FakeClient())

    with pytest.raises(ValueError, match="model_name"):
        provider.get_chat_bot("")
    with pytest.raises(ValueError, match="name"):
        provider.get_chat_bot("model", name="")
    with pytest.raises(TypeError, match="role_definition"):
        provider.get_chat_bot("model", role_definition=1)

    bot = provider.get_chat_bot("model")
    assert bot.name == "model"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_type",
    [
        OpenaiProvider,
        DeepSeekProvider,
        MoonshotProvider,
        OllamaProvider,
    ],
)
async def test_bind_tools_accepts_iterable_and_injects_schemas(
    provider_type,
):
    client = FakeClient(_completion())
    bot = provider_type(client=client).get_chat_bot("model")
    tool_iterator = (
        registered_tool
        for registered_tool in [weather_lookup, current_time]
    )

    returned_bot = bot.bind_tools(tool_iterator)
    await bot.invoke([ApixUserMessage(content="question")])

    assert returned_bot is bot
    assert client.completions.requests[0]["tools"] == [
        weather_lookup.get_schema(),
        current_time.get_schema(),
    ]


@pytest.mark.asyncio
async def test_bind_tools_accepts_tool_node_for_stream():
    client = FakeClient(FakeAsyncStream([_chunk()]))
    bot = OpenaiProvider(client=client).get_chat_bot("model")
    tool_node = ToolNode([weather_lookup])

    chunks = [
        chunk
        async for chunk in bot.bind_tools(tool_node).stream(
            [ApixUserMessage(content="question")]
        )
    ]

    assert len(chunks) == 1
    assert client.completions.requests[0]["tools"] == (
        tool_node.get_schemas()
    )


@pytest.mark.asyncio
async def test_bind_tools_replaces_and_empty_iterable_clears_binding():
    client = FakeClient(
        _completion(),
        _completion(),
        _completion(),
    )
    bot = OpenaiProvider(client=client).get_chat_bot("model")

    bot.bind_tools([weather_lookup])
    await bot.invoke([])
    bot.bind_tools([current_time])
    await bot.invoke([])
    bot.bind_tools([])
    await bot.invoke([])

    assert client.completions.requests[0]["tools"] == [
        weather_lookup.get_schema()
    ]
    assert client.completions.requests[1]["tools"] == [
        current_time.get_schema()
    ]
    assert "tools" not in client.completions.requests[2]


def test_bind_tools_validates_tool_set():
    bot = OpenaiProvider(client=FakeClient()).get_chat_bot("model")

    with pytest.raises(TypeError, match="iterable"):
        bot.bind_tools(weather_lookup)
    with pytest.raises(TypeError, match="only Tool objects"):
        bot.bind_tools([object()])
    with pytest.raises(ValueError, match="already registered"):
        bot.bind_tools([weather_lookup, weather_lookup])


@pytest.mark.asyncio
async def test_bound_tools_reject_extra_body_tools_override():
    client = FakeClient(_completion())
    bot = (
        OpenaiProvider(client=client)
        .get_chat_bot("model")
        .bind_tools([weather_lookup])
    )

    with pytest.raises(ValueError, match="extra_body.*tools"):
        await bot.invoke([], extra_body={"tools": []})

    assert client.completions.requests == []


@pytest.mark.asyncio
async def test_invoke_orders_prompts_and_converts_all_message_types():
    response = _completion()
    client = FakeClient(response)
    bot = DeepSeekProvider(client=client).get_chat_bot(
        "deepseek-chat",
        name="agent",
        role_definition="You are the role definition.",
    )
    extra_body = {"tools": [{"type": "function"}]}

    result = await bot.invoke(
        messages=[
            ApixUserMessage(content="question", name="caller"),
            ApixAiMessage(
                content=None,
                name="previous-agent",
                reasoning="previous reasoning",
                tool_calls=[
                    {
                        "call_id": "call-old",
                        "tool_name": "lookup",
                        "args": {"query": "Tokyo"},
                    }
                ],
            ),
            ApixToolMessage(
                content="tool result",
                name="lookup",
                tool_call_id="call-old",
            ),
        ],
        system_prompt=[
            ApixSystemMessage(content="outer system"),
            ApixDeveloperMessage(content="developer policy"),
        ],
        reasoning=True,
        reasoning_effort="medium",
        extra_body=extra_body,
    )

    request = client.completions.requests[0]
    assert [message["role"] for message in request["messages"]] == [
        "system",
        "system",
        "system",
        "user",
        "assistant",
        "tool",
    ]
    assert [
        message["content"]
        for message in request["messages"][:4]
    ] == [
        "outer system",
        "developer policy",
        "You are the role definition.",
        "question",
    ]
    assistant = request["messages"][4]
    assert assistant["reasoning_content"] == "previous reasoning"
    assert assistant["tool_calls"][0]["function"] == {
        "name": "lookup",
        "arguments": '{"query":"Tokyo"}',
    }
    assert request["messages"][5]["tool_call_id"] == "call-old"
    assert request["reasoning_effort"] == "medium"
    assert request["extra_body"] == {
        "tools": [{"type": "function"}],
        "thinking": {"type": "enabled"},
    }
    assert extra_body == {"tools": [{"type": "function"}]}
    assert result.name == "agent"


@pytest.mark.asyncio
async def test_openai_invoke_converts_response_and_injects_name():
    raw_message = SimpleNamespace(
        content="answer",
        refusal=None,
        reasoning_content="provider reasoning",
        tool_calls=[_tool_call()],
    )
    response = _completion(
        message=raw_message,
        finish_reason="tool_calls",
        usage={"prompt_tokens": 3, "completion_tokens": 4},
    )
    client = FakeClient(response)
    bot = OpenaiProvider(client=client).get_chat_bot(
        "gpt-test",
        name="assistant-name",
    )

    result = await bot.invoke(
        [ApixUserMessage(content="question")],
        reasoning=False,
    )

    assert isinstance(result, ApixAiMessage)
    assert result.content == "answer"
    assert result.name == "assistant-name"
    assert result.id == "completion-1"
    assert result.reasoning == "provider reasoning"
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls == [
        {
            "call_id": "call-1",
            "tool_name": "lookup",
            "args": {"query": "Tokyo"},
        }
    ]
    assert result.info == {
        "provider": "openai",
        "model": "provider-model",
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 4,
        },
    }
    assert result.timestamp == "2023-11-14T22:13:20+00:00"

    request = client.completions.requests[0]
    assert request["stream"] is False
    assert request["reasoning_effort"] == "none"


@pytest.mark.asyncio
async def test_stream_yields_named_chunks_with_reasoning_and_tool_calls():
    first = _chunk(
        delta=SimpleNamespace(
            content=None,
            reasoning_content="thinking",
            refusal=None,
            tool_calls=[
                SimpleNamespace(
                    index=0,
                    id="call-1",
                    function=SimpleNamespace(
                        name="lookup",
                        arguments='{"query":',
                    ),
                )
            ],
        )
    )
    second = _chunk(
        delta=SimpleNamespace(
            content="answer",
            reasoning_content=None,
            refusal=None,
            tool_calls=[
                SimpleNamespace(
                    index=0,
                    id=None,
                    function=SimpleNamespace(
                        name=None,
                        arguments='"Tokyo"}',
                    ),
                )
            ],
        ),
        finish_reason="tool_calls",
        usage={"total_tokens": 9},
    )
    client = FakeClient(FakeAsyncStream([first, second]))
    bot = DeepSeekProvider(client=client).get_chat_bot(
        "deepseek-reasoner",
        name="streaming-agent",
    )

    chunks = [
        chunk
        async for chunk in bot.stream(
            [ApixUserMessage(content="question")],
            reasoning=False,
        )
    ]

    assert len(chunks) == 2
    assert all(
        isinstance(chunk, ApixAiMessageChunk)
        for chunk in chunks
    )
    assert [chunk.name for chunk in chunks] == [
        "streaming-agent",
        "streaming-agent",
    ]
    assert chunks[0].reasoning_delta == "thinking"
    assert chunks[1].content_delta == "answer"

    aggregated = chunks[0] + chunks[1]
    message = aggregated.to_message(require_finished=True)
    assert message.name == "streaming-agent"
    assert message.reasoning == "thinking"
    assert message.content == "answer"
    assert message.tool_calls == [
        {
            "call_id": "call-1",
            "tool_name": "lookup",
            "args": {"query": "Tokyo"},
        }
    ]
    assert message.info["usage"] == {"total_tokens": 9}

    request = client.completions.requests[0]
    assert request["stream"] is True
    assert "reasoning_effort" not in request
    assert request["extra_body"]["thinking"] == {
        "type": "disabled"
    }


@pytest.mark.asyncio
async def test_stream_preserves_usage_only_chunk():
    usage_chunk = _chunk(
        choices=[],
        usage={"total_tokens": 2},
    )
    client = FakeClient(FakeAsyncStream([usage_chunk]))
    bot = OpenaiProvider(client=client).get_chat_bot(
        "gpt-test",
        name="agent",
    )

    chunks = [
        chunk
        async for chunk in bot.stream(
            [ApixUserMessage(content="question")]
        )
    ]

    assert len(chunks) == 1
    assert chunks[0].name == "agent"
    assert chunks[0].has_delta is False
    assert chunks[0].info["usage"] == {"total_tokens": 2}


@pytest.mark.asyncio
async def test_provider_specific_reasoning_and_developer_role():
    openai_client = FakeClient(_completion())
    openai_bot = OpenaiProvider(
        client=openai_client
    ).get_chat_bot("gpt")
    await openai_bot.invoke(
        [ApixDeveloperMessage(content="policy")],
        reasoning=True,
        reasoning_effort="low",
    )
    openai_request = openai_client.completions.requests[0]
    assert openai_request["messages"][0]["role"] == "developer"
    assert openai_request["reasoning_effort"] == "low"

    moonshot_client = FakeClient(_completion())
    moonshot_bot = MoonshotProvider(
        client=moonshot_client
    ).get_chat_bot("kimi")
    await moonshot_bot.invoke(
        [ApixDeveloperMessage(content="policy")],
        reasoning=True,
        reasoning_effort="medium",
    )
    moonshot_request = moonshot_client.completions.requests[0]
    assert moonshot_request["messages"][0]["role"] == "system"
    assert moonshot_request["reasoning_effort"] == "high"

    ollama_client = FakeClient(_completion())
    ollama_bot = OllamaProvider(
        client=ollama_client
    ).get_chat_bot("qwen")
    await ollama_bot.invoke(
        [ApixUserMessage(content="question")],
        reasoning=True,
    )
    assert (
        "reasoning_effort"
        not in ollama_client.completions.requests[0]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        ({"messages": "invalid"}, TypeError, "messages must be a list"),
        (
            {
                "messages": [],
                "system_prompt": "invalid",
            },
            TypeError,
            "system_prompt must be a list",
        ),
        (
            {
                "messages": [],
                "reasoning": "yes",
            },
            TypeError,
            "reasoning must be a bool",
        ),
        (
            {
                "messages": [],
                "reasoning_effort": "max",
            },
            ValueError,
            "reasoning_effort",
        ),
        (
            {
                "messages": [],
                "extra_body": [],
            },
            TypeError,
            "extra_body must be a dict",
        ),
        (
            {
                "messages": [ApixAiMessageChunk()],
            },
            TypeError,
            "cannot be used as model input",
        ),
    ],
)
async def test_invoke_validates_inputs(kwargs, error_type, message):
    bot = OpenaiProvider(
        client=FakeClient(_completion())
    ).get_chat_bot("gpt")

    with pytest.raises(error_type, match=message):
        await bot.invoke(**kwargs)


def test_response_validation():
    bot = OpenaiProvider(
        client=FakeClient()
    ).get_chat_bot("gpt")

    with pytest.raises(RuntimeError, match="without choices"):
        bot._to_message(_completion(choices=[]))

    with pytest.raises(RuntimeError, match="has no message"):
        bot._to_message(
            _completion(
                choices=[
                    SimpleNamespace(
                        index=0,
                        finish_reason="stop",
                        message=None,
                    )
                ]
            )
        )

    unknown_finish = bot._to_message(
        _completion(finish_reason="function_call")
    )
    assert unknown_finish.finish_reason == "unknown"


@pytest.mark.parametrize(
    ("tool_call", "message"),
    [
        (_tool_call(call_id=""), "missing a call id"),
        (_tool_call(name=""), "missing a function name"),
        (_tool_call(arguments="{"), "invalid JSON arguments"),
        (_tool_call(arguments="[]"), "JSON object"),
    ],
)
def test_complete_tool_call_validation(tool_call, message):
    bot = OpenaiProvider(
        client=FakeClient()
    ).get_chat_bot("gpt")

    with pytest.raises(ValueError, match=message):
        bot._parse_tool_calls([tool_call])


def test_tool_call_delta_validation():
    bot = OpenaiProvider(
        client=FakeClient()
    ).get_chat_bot("gpt")

    with pytest.raises(ValueError, match="index"):
        bot._parse_tool_call_deltas(
            [
                SimpleNamespace(
                    index=-1,
                    id=None,
                    function=None,
                )
            ]
        )


def test_internal_provider_value_helpers_cover_sdk_variants():
    class Usage:
        def model_dump(self, *, exclude_none):
            assert exclude_none is True
            return {"total_tokens": 3}

    class InvalidUsage:
        def model_dump(self, *, exclude_none):
            return []

    assert model_base._get_field({"value": 1}, "value") == 1
    assert model_base._model_dump(Usage()) == {
        "total_tokens": 3
    }
    assert model_base._model_dump(InvalidUsage()) == {}
    assert model_base._model_dump(object()) == {}
    assert model_base._iso_timestamp(None, empty=True) == ""
    assert "T" in model_base._iso_timestamp(None)


def test_message_conversion_rejects_unknown_message_object():
    bot = OpenaiProvider(
        client=FakeClient()
    ).get_chat_bot("gpt")

    with pytest.raises(TypeError, match="complete message objects"):
        bot._convert_message("not a message")
