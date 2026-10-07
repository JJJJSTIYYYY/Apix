from dataclasses import fields
from types import SimpleNamespace

import pytest

from apix.agent.core.bot import (
    OPENAI_CHAT_SCHEMA,
    Bot,
    CustomProfile,
    ModelProfile,
    ProfileRegistry,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ResponseField,
    ResponseLayout,
    ResponseSchema,
    StreamField,
    ToolProfile,
    resolve_model,
    resolve_provider,
)
from apix.agent.core.bot.codec.base import read_path, select


def test_register_provider_only_is_sufficient_and_registry_is_provider_scoped():
    registry = ProfileRegistry()
    registry.register_provider(
        ProviderProfile("example", endpoint="https://example.test/v1")
    )
    registry.register_provider(
        ProviderProfile("another", endpoint="https://another.test/v1")
    )
    assert (
        registry.resolve("example", "any-model").model.api_style == "chat_completions"
    )
    registry.register_model(
        "example", ModelProfile("special-*", reasoning=ReasoningProfile(mode="always"))
    )
    assert registry.resolve_model("example", "special-1").reasoning.mode == "always"
    assert registry.resolve_model("another", "special-1").reasoning.mode == "none"
    bot = Bot(
        provider="example",
        model="any-model",
        api_key="test",
        registry=registry,
        client=object(),
    )
    assert bot.build_request([])["messages"] == []


def test_model_matching_is_case_insensitive_specific_and_deterministic():
    registry = ProfileRegistry()
    registry.register_provider(
        ProviderProfile("example", endpoint="https://example.test"), aliases=("alias",)
    )
    for pattern in ("*", "model-*", "model-v2*", "model-v2-exact"):
        registry.register_model("example", ModelProfile(pattern))
    assert registry.resolve_model("alias", "MODEL-V2-EXACT").pattern == "model-v2-exact"
    assert registry.resolve_model("example", "model-v2-other").pattern == "model-v2*"
    assert registry.resolve_model("example", "unknown").pattern == "*"
    registry.register_model("example", ModelProfile("model-v2-?ther"))
    registry.register_model("example", ModelProfile("model-v2-o?her"))
    with pytest.raises(ValueError, match="ambiguous"):
        registry.resolve_model("example", "model-v2-other")


def test_profiles_are_isolated_from_registration_inputs_and_resolution_results():
    registry = ProfileRegistry()
    registry.register_provider(ProviderProfile("p", endpoint="https://example.test"))
    aliases = {"medium": "high"}
    registry.register_model(
        "p",
        ModelProfile(
            "*",
            reasoning=ReasoningProfile(
                mode="always", effort_values=("high",), effort_map=aliases
            ),
        ),
    )
    aliases["medium"] = "invalid"
    profile = registry.resolve_model("p", "m")
    assert profile.reasoning.effort_map["medium"] == "high"
    profile.reasoning.effort_map["medium"] = "changed"
    assert registry.resolve_model("p", "m").reasoning.effort_map["medium"] == "high"
    resolved = registry.resolve("p", "m")
    resolved.model.response_schema.complete.extensions["external"] = ("untrusted",)
    assert (
        "external"
        not in registry.resolve("p", "m").model.response_schema.complete.extensions
    )


def test_custom_endpoint_only_inherits_model_and_protocol_defaults():
    from apix.agent.core.bot.profile.registry import REGISTRY

    original = REGISTRY.resolve("deepseek", "deepseek-v4-flash")
    custom = REGISTRY.resolve(
        "deepseek", "deepseek-v4-flash", CustomProfile(endpoint="https://proxy.test")
    )
    assert custom.provider.endpoint == "https://proxy.test"
    assert original.model == custom.model
    assert custom.model.response_schema == OPENAI_CHAT_SCHEMA
    assert custom.model.reasoning.replay == "when_tools"
    tools = ToolProfile(supported=False)
    overridden = REGISTRY.resolve(
        "deepseek", "deepseek-v4-flash", CustomProfile(tools=tools)
    )
    assert overridden.model.reasoning == original.model.reasoning
    assert overridden.model.tools == tools


def test_protocol_defaults_and_custom_schema_are_resolved_before_building():
    registry = ProfileRegistry()
    provider = ProviderProfile("external", "anthropic", "https://example.test/v1")
    resolved = registry.resolve(provider, "anything")
    assert resolved.model.api_style == "messages"
    custom_schema = ResponseSchema(complete=ResponseLayout(content=("result", "text")))
    custom = registry.resolve(
        provider, "anything", CustomProfile(response_schema=custom_schema)
    )
    assert custom.model.response_schema == custom_schema
    with pytest.raises(ValueError, match="incompatible"):
        registry.resolve(provider, "m", CustomProfile(api_style="responses"))
    with pytest.raises(ValueError, match="protocol"):
        registry.register_provider(ProviderProfile("x", "invalid", "https://test"))
    with pytest.raises(ValueError, match="unknown provider"):
        registry.resolve_provider("missing")


def test_provider_contains_only_stable_metadata_and_builtins_are_not_marked_verified():
    from apix.agent.core.bot import PROVIDERS

    assert {field.name for field in fields(ProviderProfile)} == {
        "name",
        "protocol",
        "endpoint",
        "supports_server_state",
        "verification",
    }
    assert all(provider.verification == "community" for provider in PROVIDERS.values())
    assert resolve_provider("xiaomimimo") == resolve_provider("mimo")
    assert resolve_model("openai", "some-unknown-model").reasoning.mode == "none"
    assert resolve_model("minimax", "MiniMax-M2").reasoning.stream_mode == "incremental"
    assert resolve_model("minimax", "MiniMax-M3").reasoning.stream_mode == "incremental"


def test_model_versions_do_not_share_unsupported_efforts_or_ollama_thinking_controls():
    assert resolve_model("openai", "gpt-5").reasoning.mode == "always"
    assert "none" not in resolve_model("openai", "gpt-5").reasoning.effort_values
    assert "xhigh" not in resolve_model("openai", "gpt-5.1").reasoning.effort_values
    assert "xhigh" in resolve_model("openai", "gpt-5.2").reasoning.effort_values
    assert "max" not in resolve_model("openai", "gpt-5.2").reasoning.effort_values
    assert resolve_model("ollama", "unknown-model").reasoning.mode == "none"
    assert resolve_model("ollama", "qwen3").reasoning.effort is None
    assert resolve_model("ollama", "gpt-oss:20b").reasoning.effort_values == (
        "low",
        "medium",
        "high",
    )


@pytest.mark.parametrize(
    "replay,has_tools,expected",
    [
        ("never", False, False),
        ("never", True, False),
        ("always", False, True),
        ("always", True, True),
        ("when_tools", False, False),
        ("when_tools", True, True),
    ],
)
def test_reasoning_replay_is_explicit(replay, has_tools, expected):
    assert ReasoningProfile(replay=replay).should_replay(has_tools) is expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "invalid"},
        {"replay": "invalid"},
        {"stream_mode": "invalid"},
        {"effort_values": ("low",), "effort_map": {"medium": "high"}},
    ],
)
def test_invalid_reasoning_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        ReasoningProfile(**kwargs)


@pytest.mark.parametrize("path", [(), (0,), ("",), ("thinking", 0)])
def test_request_paths_are_nonempty_mapping_paths(path):
    with pytest.raises(ValueError):
        RequestField(path)


def test_schema_paths_support_objects_mappings_indexes_selectors_and_events():
    response = SimpleNamespace(result=[{"text": "a"}, {"text": "b"}])
    assert read_path(response, ("result", 1, "text")) == "b"
    assert read_path(response, ("result", 8)) is None
    assert read_path(response, ("result", -1)) is None
    assert read_path(response, ("missing", 0)) is None
    assert select(response, ResponseField(("result",), value=("text",))) == ["a", "b"]
    nested = {
        "output": [
            {"type": "message", "content": [{"type": "text", "text": "hi"}]},
            {"type": "reasoning", "content": []},
        ]
    }
    selector = ResponseField(
        ("output",),
        {"type": "message"},
        ResponseField(("content",), {"type": "text"}, ("text",)),
    )
    assert select(nested, selector) == ["hi"]
    event = {"type": "text.delta", "delta": "hello"}
    assert select(event, StreamField(("type",), "text.delta", ("delta",))) == "hello"
    assert select(event, StreamField(("type",), "reasoning.delta", ("delta",))) is None
