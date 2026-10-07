"""Offline contracts transcribed from the official sources in the audit document."""

from copy import deepcopy

import pytest

from apix.agent.core.bot import (
    Bot,
    CustomProfile,
    InvocationPolicy,
    ModelProfile,
    ProviderResponseError,
)
from apix.agent.core.bot.codec.base import StreamState, read_path
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixAiMessageAccumulator,
    ApixToolMessage,
    ApixUserMessage,
)
from tests.agent.sdk.test_bot import RecordingProtocol, weather


def bot_for(provider, model, **kwargs):
    return Bot(provider=provider, model=model, protocol=RecordingProtocol(), **kwargs)


@pytest.mark.parametrize(
    "provider,endpoint,style",
    [
        ("openai", "https://api.openai.com/v1", "chat_completions"),
        ("deepseek", "https://api.deepseek.com/v1", "chat_completions"),
        ("mimo", "https://api.xiaomimimo.com/v1", "chat_completions"),
        ("minimax", "https://api.minimax.cn/v1", "chat_completions"),
        ("moonshot", "https://api.moonshot.cn/v1", "chat_completions"),
        ("zai", "https://api.z.ai/api/paas/v4", "chat_completions"),
        (
            "qwen",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "chat_completions",
        ),
        ("anthropic", "https://api.anthropic.com/v1", "messages"),
        (
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta",
            "generate_content",
        ),
        ("openrouter", "https://openrouter.ai/api/v1", "chat_completions"),
        ("siliconflow", "https://api.siliconflow.cn/v1", "chat_completions"),
        ("ollama", "http://localhost:11434", "ollama_chat"),
    ],
)
def test_official_provider_endpoints_and_base_protocols(provider, endpoint, style):
    bot = bot_for(provider, "unknown-model")
    assert bot.endpoint == endpoint
    assert bot.model_profile.api_style == style
    assert bot.provider_profile.verification == "community"


@pytest.mark.parametrize(
    "provider,model,mode",
    [
        ("openai", "gpt-5-pro", "always"),
        ("openai", "gpt-5.2-pro", "always"),
        ("openai", "gpt-5.2-2025-12-11", "optional"),
        ("openai", "gpt-5.2-codex", "always"),
        ("openai", "o3-deep-research", "none"),
        ("openai", "o4-mini-deep-research", "none"),
        ("deepseek", "deepseek-flash", "optional"),
        ("mimo", "mimo-v2.5-pro", "optional"),
        ("mimo", "mimo-v2-tts", "none"),
        ("minimax", "MiniMax-M3", "optional"),
        ("minimax", "MiniMax-M3.1-Flash-Preview", "always"),
        ("moonshot", "kimi-k2-0905", "none"),
        ("moonshot", "kimi-k2-thinking", "always"),
        ("moonshot", "kimi-k2.5", "optional"),
        ("moonshot", "kimi-k2.6", "optional"),
        ("moonshot", "kimi-k2.7-code-highspeed", "always"),
        ("moonshot", "kimi-k3", "always"),
        ("zai", "glm-4-plus", "none"),
        ("zai", "glm-4.5", "optional"),
        ("zai", "glm-5.2", "optional"),
        ("zai", "glm-5.3-flash", "always"),
        ("qwen", "qwen3-coder-plus", "none"),
        ("qwen", "qwen3-235b-a22b-instruct-2507", "none"),
        ("qwen", "qwen3-235b-a22b-thinking-2507", "always"),
        ("gemini", "gemini-3-pro-image-preview", "none"),
        ("ollama", "qwen3:32b", "optional"),
        ("ollama", "qwen3-coder:30b", "none"),
        ("ollama", "gpt-oss-safeguard:20b", "none"),
    ],
)
def test_reasoning_profiles_do_not_leak_across_model_variants(provider, model, mode):
    assert bot_for(provider, model).model_profile.reasoning.mode == mode


@pytest.mark.parametrize("model", ["gpt-5.1-codex-max", "gpt-5.2-codex", "o3-pro"])
def test_specialized_openai_models_keep_responses_without_guessing_effort(model):
    bot = bot_for("openai", model)
    request = bot.build_request([])
    assert "input" in request and "messages" not in request
    assert request["store"] is False
    assert request["include"] == ["reasoning.encrypted_content"]
    assert "reasoning" not in request
    with pytest.raises(ValueError, match="effort"):
        bot.build_request([], reasoning_effort="none")


@pytest.mark.parametrize(
    "provider,model,effort,path,expected",
    [
        ("openai", "gpt-5-pro", "high", ("reasoning", "effort"), "high"),
        ("openai", "gpt-5.2-pro", "xhigh", ("reasoning", "effort"), "xhigh"),
        ("deepseek", "deepseek-flash", "minimal", ("reasoning_effort",), "low"),
        ("deepseek", "deepseek-v4-flash", "xhigh", ("reasoning_effort",), "high"),
        ("deepseek", "deepseek-v4-pro", "ultra", ("reasoning_effort",), "max"),
        ("minimax", "MiniMax-M3.1-Flash-Preview", "max", ("reasoning_effort",), "max"),
        ("moonshot", "kimi-k3", "low", ("reasoning_effort",), "low"),
        ("zai", "glm-5.2", "xhigh", ("reasoning_effort",), "max"),
        ("zai", "glm-5.3", "max", ("reasoning_effort",), "max"),
        ("anthropic", "claude-sonnet-4-6", "max", ("output_config", "effort"), "max"),
        ("anthropic", "claude-opus-4-7", "xhigh", ("output_config", "effort"), "xhigh"),
        (
            "gemini",
            "gemini-3.1-pro-preview",
            "medium",
            ("generationConfig", "thinkingConfig", "thinkingLevel"),
            "medium",
        ),
        (
            "gemini",
            "gemini-3-flash-preview",
            "minimal",
            ("generationConfig", "thinkingConfig", "thinkingLevel"),
            "minimal",
        ),
        (
            "siliconflow",
            "deepseek-ai/DeepSeek-V4-Flash",
            "xhigh",
            ("reasoning_effort",),
            "max",
        ),
        ("ollama", "gpt-oss:20b", "high", ("think",), "high"),
    ],
)
def test_official_effort_paths_and_explicit_aliases(
    provider, model, effort, path, expected
):
    request = bot_for(provider, model).build_request([], reasoning_effort=effort)
    assert read_path(request, path) == expected


@pytest.mark.parametrize(
    "provider,model,kwargs",
    [
        ("openai", "gpt-5-pro", {"reasoning_effort": "low"}),
        ("openai", "gpt-5.2-pro", {"reasoning": False}),
        ("openai", "gpt-5.2-pro", {"reasoning_effort": "none"}),
        ("minimax", "MiniMax-M2.7", {"reasoning": False}),
        ("minimax", "MiniMax-M3", {"reasoning_effort": "high"}),
        ("minimax", "MiniMax-M3.1-Flash-Preview", {"reasoning": False}),
        ("moonshot", "kimi-k2-thinking", {"reasoning": False}),
        ("moonshot", "kimi-k2.7-code", {"reasoning": False}),
        ("moonshot", "kimi-k3", {"reasoning_effort": "medium"}),
        ("zai", "glm-5.3", {"reasoning": False}),
        ("anthropic", "claude-opus-4-6", {"reasoning_effort": "xhigh"}),
        ("gemini", "gemini-3-pro-preview", {"reasoning_effort": "medium"}),
        ("qwen", "qwen3-32b", {}),
        ("qwen", "qwen3-235b-a22b-thinking-2507", {"reasoning": False}),
    ],
)
def test_invalid_combinations_fail_before_transport(provider, model, kwargs):
    bot = bot_for(provider, model)
    with pytest.raises(ValueError):
        bot.build_request([], **kwargs)
    assert bot._protocol.calls == []


@pytest.mark.parametrize(
    "provider,model,reasoning,choice,allowed",
    [
        ("deepseek", "deepseek-flash", True, "weather", False),
        ("deepseek", "deepseek-flash", False, "weather", True),
        ("moonshot", "kimi-k3", True, "required", True),
        ("moonshot", "kimi-k3", True, "weather", False),
        ("qwen", "qwen3.5-plus", True, "required", False),
        ("qwen", "qwen3.5-plus", False, "required", False),
        ("qwen", "qwen3.5-plus", True, "weather", False),
        ("qwen", "qwen3.5-plus", False, "weather", True),
        ("zai", "glm-5.2", True, "none", False),
        ("zai", "glm-5.2", False, "weather", False),
        ("anthropic", "claude-opus-4-6", True, "weather", True),
        ("ollama", "qwen3", True, "required", False),
    ],
)
def test_model_specific_tool_choice_constraints(
    provider, model, reasoning, choice, allowed
):
    bot = bot_for(provider, model)
    kwargs = {"tools": [weather], "reasoning": reasoning, "tool_choice": choice}
    if allowed:
        bot.build_request([], **kwargs)
    else:
        with pytest.raises(ValueError, match="tool_choice"):
            bot.build_request([], **kwargs)


@pytest.mark.parametrize(
    "provider,model", [("deepseek", "deepseek-flash"), ("mimo", "mimo-v2.5")]
)
def test_tools_require_all_prior_reasoning_not_only_tool_call_messages(provider, model):
    bot = bot_for(provider, model)
    messages = [
        ApixUserMessage(content="first question"),
        ApixAiMessage(content="first answer", reasoning="prior thinking"),
        ApixUserMessage(content="now use a tool"),
        ApixAiMessage(
            reasoning="tool thinking",
            tool_calls=[
                {"call_id": "c1", "tool_name": "weather", "args": {"city": "Paris"}}
            ],
        ),
        ApixToolMessage(tool_call_id="c1", name="weather", content="sunny"),
    ]
    before = deepcopy(messages)
    request = bot.build_request(messages, tools=[weather])
    assert request["messages"][1]["reasoning_content"] == "prior thinking"
    assert request["messages"][3]["reasoning_content"] == "tool thinking"
    assert all(
        "reasoning_content" not in item
        for item in bot.build_request(messages, tools=[])["messages"]
    )
    assert messages == before


def test_reasoning_disable_aliases_and_anthropic_effort_without_thinking():
    request = bot_for("deepseek", "deepseek-flash").build_request(
        [], reasoning_effort="none"
    )
    assert request["thinking"]["type"] == "disabled"
    request = bot_for("zai", "glm-5.2").build_request([], reasoning_effort="minimal")
    assert request["thinking"]["type"] == "disabled"
    request = bot_for("anthropic", "claude-opus-4-7").build_request(
        [], reasoning=False, reasoning_effort="high"
    )
    assert request["thinking"] == {"type": "disabled"}
    assert request["output_config"]["effort"] == "high"


def test_model_request_defaults_merge_in_order_without_mutating_inputs():
    profile = ModelProfile(request_options={"temperature": 0.1, "custom": {"a": 1}})
    policy = InvocationPolicy(request_options={"temperature": 0.2, "custom": {"b": 2}})
    bot = bot_for("openai", "unknown", model_profile=profile, policy=policy)
    request = bot.build_request(
        [], request_options={"temperature": 0.3}, extra_body={"temperature": 0.4}
    )
    assert request["temperature"] == 0.4
    assert request["custom"] == {"a": 1, "b": 2}
    request["custom"]["a"] = 9
    assert profile.request_options["custom"]["a"] == 1
    assert bot.build_request([])["custom"]["a"] == 1
    bot = bot_for(
        "minimax",
        "MiniMax-M3",
        custom_profile=CustomProfile(endpoint="https://proxy.test/v1"),
    )
    assert bot.build_request([])["reasoning_split"] is True
    assert bot.build_request([], reasoning=False)["thinking"]["type"] == "disabled"


def test_gemini_thought_summaries_and_level_budget_exclusion():
    bot = bot_for("gemini", "gemini-3.1-pro-preview")
    request = bot.build_request([], reasoning_effort="medium")
    assert request["generationConfig"]["thinkingConfig"] == {
        "includeThoughts": True,
        "thinkingLevel": "medium",
    }
    budget = {"generationConfig": {"thinkingConfig": {"thinkingBudget": 1024}}}
    with pytest.raises(ValueError, match="thinkingBudget"):
        bot.build_request([], reasoning_effort="medium", request_options=budget)
    assert (
        bot.build_request([], request_options=budget)["generationConfig"][
            "thinkingConfig"
        ]["thinkingBudget"]
        == 1024
    )
    assert (
        bot_for("qwen", "qwen3-32b").build_request([], reasoning=False)[
            "enable_thinking"
        ]
        is False
    )
    assert (
        bot_for("qwen", "qwen3-32b").build_request([], stream=True)["enable_thinking"]
        is True
    )


@pytest.mark.parametrize(
    "options", [{"output_config": {"effort": "high"}}, {"reasoning": {"enabled": True}}]
)
def test_raw_options_cannot_bypass_reasoning_capability_validation(options):
    with pytest.raises(ValueError, match="explicit"):
        bot_for("openai", "unknown").build_request([], extra_body=options)


@pytest.mark.asyncio
async def test_minimax_current_incremental_reasoning_format():
    bot = Bot(
        provider="minimax",
        model="MiniMax-M3",
        protocol=RecordingProtocol(
            events=[
                {
                    "choices": [
                        {
                            "delta": {"reasoning_content": value},
                            "finish_reason": "stop" if value == "B" else None,
                        }
                    ]
                }
                for value in ("A", "B")
            ]
        ),
    )
    accumulator = ApixAiMessageAccumulator()
    async for chunk in bot.stream([]):
        accumulator.add(chunk)
    assert accumulator.to_message(require_finished=True).reasoning == "AB"
    assert bot._protocol.calls[0]["reasoning_split"] is True


@pytest.mark.asyncio
async def test_openrouter_reasoning_details_stream_and_replay_are_lossless():
    details = [
        [
            {
                "index": 0,
                "id": "r1",
                "type": "reasoning.text",
                "text": "A",
                "signature": None,
            }
        ],
        [{"index": 0, "text": "B", "signature": "sig"}],
        [{"index": 1, "id": "r2", "type": "reasoning.encrypted", "data": "opaque"}],
    ]
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "reasoning": "A" if i == 0 else "B" if i == 1 else "",
                        "reasoning_details": value,
                    }
                }
            ]
        }
        for i, value in enumerate(details)
    ] + [{"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}]}]
    bot = Bot(
        provider="openrouter",
        model="routed/model",
        protocol=RecordingProtocol(events=events),
    )
    for _ in range(2):
        chunks = [chunk async for chunk in bot.stream([])]
        accumulator = ApixAiMessageAccumulator()
        for chunk in chunks:
            accumulator.add(chunk)
        message = accumulator.to_message(require_finished=True)
        assert message.reasoning == "AB"
        assert message.extensions["reasoning_details"] == [
            {
                "index": 0,
                "id": "r1",
                "type": "reasoning.text",
                "text": "AB",
                "signature": "sig",
            },
            {"index": 1, "id": "r2", "type": "reasoning.encrypted", "data": "opaque"},
        ]
        replayed = bot.build_request([message])["messages"][0]
        assert replayed["reasoning"] == "AB"
        assert replayed["reasoning_details"] == message.extensions["reasoning_details"]
        assert chunks[0].extensions["reasoning_details"][0]["text"] == "A"


def test_openrouter_complete_opaque_reasoning_does_not_require_visible_text():
    bot = bot_for("openrouter", "routed/model")
    detail = {"type": "reasoning.encrypted", "id": "r1", "data": "opaque"}
    raw = {
        "choices": [
            {"message": {"reasoning_details": [detail]}, "finish_reason": "length"}
        ]
    }
    message = bot.convert_message_to_apix(raw)
    assert message.reasoning is None
    assert message.finish_reason == "length"
    assert message.extensions["reasoning_details"] == [detail]
    assert bot.build_request([message])["messages"][0]["reasoning_details"] == [detail]


@pytest.mark.parametrize(
    "detail",
    [
        {"index": []},
        {"index": -1},
        {"index": True},
        {"id": []},
        {"index": 0, "text": []},
        {"index": 0, "id": "changed"},
        {"index": 0, "type": "reasoning.encrypted"},
    ],
)
def test_malformed_or_changed_reasoning_detail_blocks_are_rejected(detail):
    bot = bot_for("openrouter", "routed/model")
    state = StreamState()
    context = {"provider": "openrouter", "model": "routed/model"}
    bot._codec.decode_stream(
        {
            "choices": [
                {
                    "delta": {
                        "reasoning_details": [
                            {
                                "index": 0,
                                "id": "original",
                                "type": "reasoning.text",
                                "text": "A",
                            }
                        ]
                    }
                }
            ]
        },
        state,
        **context,
    )
    with pytest.raises(ProviderResponseError):
        bot._codec.decode_stream(
            {"choices": [{"delta": {"reasoning_details": [detail]}}]}, state, **context
        )
