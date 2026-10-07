"""Public Bot contracts, independent of provider implementation classes."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from importlib import import_module

import pytest

from apix.agent.core.bot import (
    PROVIDERS,
    AnthropicBot,
    BaseBot,
    Bot,
    CustomBot,
    CustomProfile,
    DeepSeekBot,
    GeminiBot,
    InvocationPolicy,
    MiniMaxBot,
    ModelProfile,
    MoonshotBot,
    OllamaBot,
    OpenAIBot,
    OpenRouterBot,
    ProviderResponseError,
    QwenBot,
    ReasoningProfile,
    RequestField,
    SiliconFlowBot,
    ToolProfile,
    XiaomiMIMOBot,
    ZAIBot,
)
from apix.agent.core.bot.protocol import PROTOCOLS, BaseProtocol
from apix.agent.core.tool import ToolNode, tool
from apix.agent.core.utils.message import (
    ApixAiMessageAccumulator,
    ApixAiMessageChunk,
    ApixSystemMessage,
    ApixToolMessage,
    ApixUserMessage,
)


class RecordingProtocol(BaseProtocol):
    def __init__(self, *responses, events=()):
        self.responses = list(responses)
        self.events = events
        self.calls = []
        self.closed = False
        self.stream_closed = False

    async def invoke(self, request):
        self.calls.append(deepcopy(request))
        return self.responses.pop(0)

    async def stream(self, request):
        self.calls.append(deepcopy(request))
        try:
            for event in self.events:
                await asyncio.sleep(0)
                yield event
        finally:
            self.stream_closed = True

    async def aclose(self):
        self.closed = True


@tool
def weather(city: str) -> str:
    """Get the weather for a city."""
    return f"sunny in {city}"


def completion(content="answer", reasoning=None, calls=None):
    return {
        "model": "returned-model",
        "id": "response-id",
        "choices": [
            {
                "message": {
                    "content": content,
                    "reasoning_content": reasoning,
                    "tool_calls": calls,
                },
                "finish_reason": "tool_calls" if calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3},
    }


def make_bot(**kwargs):
    return Bot(
        provider="deepseek",
        model="deepseek-v4-flash",
        protocol=RecordingProtocol(),
        **kwargs,
    )


PROVIDER_BOT_CASES = (
    (OpenAIBot, "openai", "gpt-5.2"),
    (DeepSeekBot, "deepseek", "deepseek-v4-flash"),
    (MiniMaxBot, "minimax", "MiniMax-M3"),
    (XiaomiMIMOBot, "mimo", "mimo-v2.5"),
    (OllamaBot, "ollama", "qwen3"),
    (AnthropicBot, "anthropic", "claude-opus-4-7"),
    (GeminiBot, "gemini", "gemini-3.1-pro-preview"),
    (MoonshotBot, "moonshot", "kimi-k3"),
    (ZAIBot, "zai", "glm-5.3"),
    (QwenBot, "qwen", "qwen3.5-plus"),
    (OpenRouterBot, "openrouter", "routed/model"),
    (SiliconFlowBot, "siliconflow", "deepseek-ai/DeepSeek-V4-Flash"),
)


@pytest.mark.parametrize("cls,provider,model", PROVIDER_BOT_CASES)
@pytest.mark.parametrize("endpoint", [None, "https://proxy.test/v1"])
def test_public_entry_and_provider_constructors_resolve_same_profiles(
    cls, provider, model, endpoint
):
    assert Bot is BaseBot
    named = cls(model=model, endpoint=endpoint, protocol=RecordingProtocol())
    unified = Bot(
        provider=provider, model=model, endpoint=endpoint, protocol=RecordingProtocol()
    )
    assert named.model_profile == unified.model_profile
    assert named.provider_profile == unified.provider_profile
    assert named.endpoint == unified.endpoint
    assert named.build_request([]) == unified.build_request([])
    assert named.build_request(
        [], tools=[weather], stream=True
    ) == unified.build_request([], tools=[weather], stream=True)
    assert {name for name in cls.__dict__ if not name.startswith("_")} == {"provider"}


def test_all_builtin_providers_have_public_module_and_package_bot_exports():
    package = import_module("apix.agent.core.bot")
    assert {provider for _, provider, _ in PROVIDER_BOT_CASES} == set(PROVIDERS)
    for cls, provider, _ in PROVIDER_BOT_CASES:
        assert cls.provider == provider
        assert cls.__name__ in package.__all__
        assert getattr(package, cls.__name__) is cls
        assert getattr(import_module(cls.__module__), cls.__name__) is cls


@pytest.mark.parametrize("cls,provider,model", PROVIDER_BOT_CASES)
def test_provider_constructors_select_registered_transport_without_network(
    cls, provider, model
):
    client = object()
    bot = cls(model=model, api_key="test", client=client)
    assert isinstance(bot._protocol, PROTOCOLS[PROVIDERS[provider].protocol])
    assert bot._protocol.client is client


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"model": ""}, ValueError),
        ({"endpoint": ""}, ValueError),
        ({"api_key": None}, TypeError),
        ({"model_profile": {}}, TypeError),
        ({"custom_profile": {}}, TypeError),
        ({"policy": {}}, TypeError),
        ({"role_schema": {}}, TypeError),
        ({"role_schema": {"name": "a", "definition": "x", "title": 3}}, TypeError),
    ],
)
def test_constructor_validation(kwargs, error):
    defaults = {
        "model": "m",
        "endpoint": "https://example.test/v1",
        "protocol": RecordingProtocol(),
    }
    defaults.update(kwargs)
    with pytest.raises(error):
        Bot(**defaults)


def test_custom_provider_requires_endpoint_and_defaults_to_chat():
    with pytest.raises(ValueError, match="endpoint"):
        CustomBot(model="m", protocol=RecordingProtocol())
    bot = CustomBot(
        model="m", endpoint="https://example.test/v1/", protocol=RecordingProtocol()
    )
    assert bot.endpoint == "https://example.test/v1"
    assert bot.model_profile.api_style == "chat_completions"
    assert bot.build_request([ApixUserMessage(content="hi")]) == {
        "model": "m",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
    }


def test_bind_tools_filters_copies_replaces_and_accepts_tool_nodes():
    bot = make_bot()
    assert bot.bind_tools([weather]) is bot
    copy = bot.tool_schemas
    copy[0]["function"]["name"] = "changed"
    assert bot.tool_schemas[0]["function"]["name"] == "weather"
    bot.bind_tools([weather], tool_permission_set=set())
    assert bot.tool_schemas == []
    bot.bind_tools(ToolNode(weather), tool_permission_set={"weather"})
    assert len(bot.tool_schemas) == 1
    bot.bind_tools(ToolNode(weather), tool_permission_set=set())
    assert bot.tool_schemas == []
    bot.bind_tools([])
    for invalid in ([object()], [None], "weather", 12, {"type": "web_search"}):
        with pytest.raises(TypeError):
            bot.bind_tools(invalid)
    with pytest.raises(ValueError, match="unique"):
        bot.bind_tools([weather, weather])


def test_role_schema_and_message_order_are_isolated():
    role = {"name": " Alice ", "title": None, "definition": "Be concise."}
    bot = make_bot().bind_role_schema(role)
    role["name"] = "changed"
    assert bot.name == "Alice"
    request = bot.build_request(
        [ApixUserMessage(content="question")], [ApixSystemMessage(content="global")]
    )
    assert request["messages"][0] == {"role": "system", "content": "global"}
    assert "Your name: Alice" in request["messages"][1]["content"]
    assert request["messages"][2]["content"] == "question"
    for messages, system in (((), None), ([], ())):
        with pytest.raises(TypeError):
            bot.build_request(messages, system)
    with pytest.raises(TypeError, match="complete"):
        bot.build_request([ApixAiMessageChunk(content_delta="partial")])


@pytest.mark.asyncio
async def test_invoke_uses_unified_messages_and_never_executes_tools():
    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "weather", "arguments": '{"city":"Tokyo"}'},
    }
    transport = RecordingProtocol(completion("", "think", [call]), completion("sunny"))
    bot = Bot(
        provider="deepseek", model="deepseek-v4-flash", protocol=transport
    ).bind_tools([weather])
    prompt = ApixUserMessage(content="weather?")
    response = await bot.invoke([prompt], reasoning_effort="medium")
    assert len(transport.calls) == 1
    assert response.reasoning == "think"
    assert response.tool_calls == [
        {"call_id": "c1", "tool_name": "weather", "args": {"city": "Tokyo"}}
    ]
    assert response.finish_reason == "tool_calls"
    assert response.metadata["usage"] == {
        "input_tokens": 2,
        "output_tokens": 3,
        "total_tokens": 5,
    }
    assert response.metadata["model"] == "returned-model"
    assert response.metadata["duration"] >= 0
    result = await weather.func(**response.tool_calls[0]["args"])
    final = await bot.invoke(
        [prompt, response, ApixToolMessage(tool_call_id="c1", content=result)]
    )
    assert final.content == "sunny"
    assert transport.calls[1]["messages"][1]["reasoning_content"] == "think"
    assert transport.calls[1]["messages"][2]["content"] == "sunny in Tokyo"
    assert transport.calls[0]["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_call_local_tools_do_not_mutate_bound_tools():
    transport = RecordingProtocol(completion(), completion())
    bot = Bot(provider="deepseek", model="deepseek-v4", protocol=transport).bind_tools(
        [weather]
    )
    await bot.invoke([], tools=[])
    await bot.invoke([])
    assert "tools" not in transport.calls[0]
    assert transport.calls[1]["tools"][0]["function"]["name"] == "weather"


@pytest.mark.parametrize(
    "options",
    [
        {"previous_response_id": "r"},
        {"conversation": "c"},
        {"store": True},
        {"tools": [{"type": "web_search"}]},
        {"messages": []},
        {"input": []},
        {"contents": []},
        {"instructions": "hidden"},
        {"builtin_tools": []},
        {"mcp": {}},
        {"web_search": True},
        {"extra_body": {"store": True}},
        {"thinking": {"type": "disabled"}},
        {"reasoning_effort": "max"},
    ],
)
@pytest.mark.parametrize("parameter", ["request_options", "extra_body"])
def test_controlled_context_and_reasoning_cannot_be_bypassed(options, parameter):
    with pytest.raises(ValueError):
        make_bot().build_request([], **{parameter: options})


def test_policy_request_options_are_validated_and_invocation_wins_without_mutation():
    options = {"temperature": 0.2, "custom": {"a": 1, "b": 1}}
    bot = make_bot(policy=InvocationPolicy(request_options=options))
    options["custom"]["a"] = 99
    request = bot.build_request(
        [], request_options={"custom": {"b": 2}}, extra_body={"custom": {"c": 3}}
    )
    assert request["custom"] == {"a": 1, "b": 2, "c": 3}
    request["custom"]["a"] = 10
    assert bot.build_request([])["custom"]["a"] == 1
    with pytest.raises(ValueError):
        make_bot(policy=InvocationPolicy(request_options={"tools": []})).build_request(
            []
        )
    for kwargs in (
        {"store": True},
        {"use_server_state": True},
        {"timeout": 0},
        {"max_retries": -1},
    ):
        with pytest.raises(ValueError):
            InvocationPolicy(**kwargs)


@pytest.mark.parametrize(
    "reasoning,effort,valid",
    [
        (True, "high", True),
        (True, "medium", True),
        (True, "unsupported", False),
        (False, "low", False),
        (False, None, True),
        (None, "max", True),
    ],
)
def test_reasoning_effort_is_explicitly_validated(reasoning, effort, valid):
    if valid:
        result = make_bot().build_request(
            [], reasoning=reasoning, reasoning_effort=effort
        )
        assert result["thinking"]["type"] == (
            "disabled" if reasoning is False else "enabled"
        )
    else:
        with pytest.raises(ValueError):
            make_bot().build_request([], reasoning=reasoning, reasoning_effort=effort)


def test_reasoning_modes_and_tool_restrictions_fail_before_dispatch():
    for mode, value in (("none", True), ("always", False)):
        bot = make_bot(
            model_profile=ModelProfile(reasoning=ReasoningProfile(mode=mode))
        )
        with pytest.raises(ValueError, match="reasoning"):
            bot.build_request([], reasoning=value)
    bot = make_bot().bind_tools([weather])
    for choice in ("required", "weather"):
        with pytest.raises(ValueError, match="tool_choice"):
            bot.build_request([], reasoning=True, tool_choice=choice)
        request = bot.build_request([], reasoning=False, tool_choice=choice)
        assert request["tool_choice"]
    with pytest.raises(ValueError, match="unbound"):
        bot.build_request([], reasoning=False, tool_choice="missing")
    profile = replace(bot.model_profile, tools=ToolProfile(supported=False))
    with pytest.raises(ValueError, match="function tools"):
        make_bot(model_profile=profile).build_request([], tools=[weather])
    profile = replace(bot.model_profile, tools=ToolProfile(parallel=False))
    limited = make_bot(model_profile=profile)
    assert limited.build_request([], tools=[weather])["parallel_tool_calls"] is False
    with pytest.raises(ValueError, match="parallel"):
        limited.build_request([], tools=[weather], parallel_tool_calls=True)
    profile = replace(bot.model_profile, tools=ToolProfile(choice_modes=("required",)))
    with pytest.raises(ValueError, match="auto"):
        make_bot(model_profile=profile).build_request([], tools=[weather])


@pytest.mark.parametrize("parameter", ["request_options", "extra_body"])
@pytest.mark.parametrize("value", [[], "", 0, False])
def test_empty_nonmapping_request_options_are_rejected(parameter, value):
    with pytest.raises(TypeError, match="mappings"):
        make_bot().build_request([], **{parameter: value})


@pytest.mark.asyncio
async def test_chat_stream_aggregates_tool_arguments_and_terminal_usage():
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "content": "hello",
                        "reasoning_content": "why ",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "c1",
                                "function": {
                                    "name": "weather",
                                    "arguments": '{"city":',
                                },
                            }
                        ],
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": '"Tokyo"}'}}
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {"choices": [], "usage": {"prompt_tokens": 2, "completion_tokens": 3}},
    ]
    transport = RecordingProtocol(events=events)
    bot = Bot(provider="deepseek", model="deepseek-v4", protocol=transport)
    chunks = [chunk async for chunk in bot.stream([])]
    assert len({chunk.message_uid for chunk in chunks}) == 1
    accumulator = ApixAiMessageAccumulator()
    for chunk in chunks:
        accumulator.add(chunk)
    response = accumulator.to_message(require_finished=True)
    assert response.content == "hello"
    assert response.reasoning == "why "
    assert response.tool_calls[0]["args"] == {"city": "Tokyo"}
    assert response.metadata["usage"]["total_tokens"] == 5
    assert transport.calls[0]["stream_options"] == {"include_usage": True}
    assert transport.stream_closed


def test_effort_only_reasoning_controls_and_contradictory_none_are_validated():
    profile = ModelProfile(
        reasoning=ReasoningProfile(
            mode="optional",
            effort_values=("none", "low", "high"),
            effort=RequestField(("effort",)),
        )
    )
    bot = make_bot(model_profile=profile)
    assert bot.build_request([], reasoning=False)["effort"] == "none"
    assert bot.build_request([], reasoning_effort="high")["effort"] == "high"
    with pytest.raises(ValueError, match="explicit"):
        bot.build_request([], reasoning=True)
    with pytest.raises(ValueError, match="conflicts"):
        bot.build_request([], reasoning=True, reasoning_effort="none")
    incomplete = make_bot(
        model_profile=ModelProfile(reasoning=ReasoningProfile(mode="optional"))
    )
    with pytest.raises(ValueError, match="configured request control"):
        incomplete.build_request([])


@pytest.mark.parametrize(
    "options",
    [
        {"enable_search": True},
        {"web_search_options": {}},
        {"cachedContent": "server-context"},
        {"conversation_id": "conversation"},
        {"reasoning_effort": "high"},
        {"thinking": {"type": "enabled"}},
        {"reasoning": {"effort": "high"}},
        {"think": True},
        {"enable_thinking": True},
    ],
)
def test_unknown_models_cannot_enable_state_native_search_or_reasoning_with_raw_options(
    options,
):
    bot = CustomBot(
        model="unknown", endpoint="https://example.test", protocol=RecordingProtocol()
    )
    with pytest.raises(ValueError):
        bot.build_request([], extra_body=options)


@pytest.mark.asyncio
async def test_cumulative_reasoning_is_normalized_per_stream_and_bad_prefix_fails():
    from apix.agent.core.bot.providers.minimax import DETAILS_SCHEMA

    events = [
        {
            "choices": [
                {
                    "delta": {"reasoning_details": [{"text": value}]},
                    "finish_reason": "stop" if value == "ABC" else None,
                }
            ]
        }
        for value in ("A", "AB", "ABC")
    ]
    bot = MiniMaxBot(
        model="MiniMax-M3",
        protocol=RecordingProtocol(events=events),
        custom_profile=CustomProfile(
            reasoning=ReasoningProfile(
                mode="always", replay="always", stream_mode="cumulative"
            ),
            response_schema=DETAILS_SCHEMA,
        ),
    )
    for _ in range(2):
        chunks = [chunk async for chunk in bot.stream([])]
        assert [chunk.reasoning_delta for chunk in chunks] == ["A", "B", "C"]
    bot._protocol.events = events[:1] + [
        {"choices": [{"delta": {"reasoning_details": [{"text": "X"}]}}]}
    ]
    with pytest.raises(ProviderResponseError, match="prefix"):
        _ = [chunk async for chunk in bot.stream([])]


@pytest.mark.asyncio
async def test_truncated_stream_raises_and_consumer_close_releases_transport():
    transport = RecordingProtocol(
        events=[{"choices": [{"delta": {"content": "partial"}}]}]
    )
    bot = Bot(provider="deepseek", model="deepseek-v4", protocol=transport)
    with pytest.raises(ProviderResponseError, match="completion event"):
        _ = [chunk async for chunk in bot.stream([])]
    assert transport.stream_closed
    transport.stream_closed = False
    stream = bot.stream([])
    assert (await anext(stream)).content_delta == "partial"
    await stream.aclose()
    assert transport.stream_closed
    async with bot:
        pass
    assert transport.closed
