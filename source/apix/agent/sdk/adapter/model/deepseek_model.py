"""DeepSeek chat provider."""

from typing import ClassVar

from apix.agent.sdk.adapter.model.base import (
    OpenAICompatibleChatBot,
    OpenAICompatibleProvider,
    ReasoningEffort,
)
from apix.config.base_config import PROVIDER_BASE_URL


class DeepSeekChatBot(OpenAICompatibleChatBot):
    """A named DeepSeek chat bot."""

    supports_reasoning_content = True
    thinking_switch = True
    reasoning_effort_map: ClassVar[dict[ReasoningEffort, str]] = {
        "low": "low",
        "medium": "medium",
        "high": "high",
    }


class DeepSeekProvider(
    OpenAICompatibleProvider[DeepSeekChatBot]
):
    """Create :class:`DeepSeekChatBot` instances."""

    provider = "deepseek"
    api_key_env = "DEEPSEEK_API_KEY"
    default_base_url = PROVIDER_BASE_URL.get(
        "deepseek",
        "https://api.deepseek.com/v1",
    )
    chat_bot_class = DeepSeekChatBot
        
