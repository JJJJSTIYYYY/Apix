"""Opt-in provider smoke tests; credentials are supplied by the runner."""
import os

import pytest

from apix.agent.core.bot import ApixBot, ModelProfile, ProviderProfile
from apix.agent.core.utils.message import ApixUserMessage

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(name) for name in ("APIX_LIVE_PROTOCOL", "APIX_LIVE_MODEL", "APIX_LIVE_API_KEY")),
    reason="Set APIX_LIVE_PROTOCOL, APIX_LIVE_MODEL and APIX_LIVE_API_KEY to enable paid tests",
)


@pytest.mark.parametrize("streaming", [False, True])
async def test_live_chat(streaming):
    bot = ApixBot(provider=ProviderProfile(protocol=os.environ["APIX_LIVE_PROTOCOL"],
                  api_key=os.environ["APIX_LIVE_API_KEY"], base_url=os.environ.get("APIX_LIVE_ENDPOINT")),
                  model=ModelProfile(model=os.environ["APIX_LIVE_MODEL"], max_tokens=100))
    history = [ApixUserMessage(content="Reply with exactly: OK")]
    if streaming:
        stream = await bot.stream(history)
        async with stream:
            async for event in stream:
                assert "choices" in event
        assert stream.result["content"]
    else:
        assert (await bot.invoke(history)).content
