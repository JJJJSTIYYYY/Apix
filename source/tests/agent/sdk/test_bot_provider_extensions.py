"""Provider-specific generation options are delegated to the library."""
from unittest.mock import AsyncMock

import pytest
from my_llm import ModelProfile, ProviderProfile
from apix.agent.core.bot import ApixBot


@pytest.mark.asyncio
async def test_provider_options_pass_to_library_without_native_request_translation(monkeypatch):
    bot = ApixBot(provider=ProviderProfile(protocol="openai_chat", api_key="test",
                  reasoning_enable_parameter={"extra_body": {"thinking": {"type": "enabled"}}},
                  replay_reasoning_content_when_tool_calls=True),
                  model=ModelProfile(model="test", supports_function_calling=True))
    generate = AsyncMock(return_value={"role": "assistant", "content": "answer"})
    monkeypatch.setattr(bot.llm, "generate", generate)
    await bot.invoke([{"role": "user", "content": "hi"}], reasoning=True,
                     extra_body={"temperature": 0.2})
    assert generate.await_args.kwargs["reasoning"] is True
    assert generate.await_args.kwargs["extra_body"] == {"temperature": 0.2}
