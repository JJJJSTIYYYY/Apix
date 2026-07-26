"""Moonshot/Kimi chat provider."""

from typing import ClassVar

from apix.agent.sdk.adapter.model.base_model import (
    OpenAICompatibleChatBot,
    OpenAICompatibleProvider,
    ReasoningEffort,
)
from apix.config.base_config import PROVIDER_BASE_URL


class MoonshotChatBot(OpenAICompatibleChatBot):
    """A named Moonshot/Kimi chat bot."""

    supports_reasoning_content = True
    reasoning_effort_map: ClassVar[dict[ReasoningEffort, str]] = {
        "low": "low",
        "medium": "high",
        "high": "high",
    }


class MoonshotProvider(
    OpenAICompatibleProvider[MoonshotChatBot]
):
    """Create :class:`MoonshotChatBot` instances."""

    provider = "moonshot"
    api_key_env = "MOONSHOT_API_KEY"
    default_base_url = PROVIDER_BASE_URL.get(
        "moonshot",
        "https://api.moonshot.cn/v1",
    )
    chat_bot_class = MoonshotChatBot
