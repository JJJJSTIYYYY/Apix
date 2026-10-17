"""Model/provider configuration is wholly owned by my-llm-py."""
from dataclasses import replace

from my_llm import ModelProfile, ProviderProfile
from apix.agent.core.bot import ApixBot


def test_profile_configuration_and_nested_values_are_isolated():
    body = {"thinking": {"type": "enabled"}}
    provider = ProviderProfile(protocol="openai_chat", api_key="test", extra_body=body)
    model = ModelProfile(model="test", supports_function_calling=True)
    bot = ApixBot(provider=provider, model=model)
    body["thinking"]["type"] = "disabled"
    assert bot.llm.resolved_profile.get("extra_body") == {"thinking": {"type": "enabled"}}
    other = ApixBot(provider=replace(provider, protocol="anthropic"), model=model)
    assert other.llm.stdio_protocol == "openai_chat"
    assert other.llm.provider.protocol == "anthropic"
