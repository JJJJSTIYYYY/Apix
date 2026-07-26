"""OpenAI chat provider."""

from typing import ClassVar

from apix.agent.sdk.adapter.model.base import (
    OpenAICompatibleChatBot,
    OpenAICompatibleProvider,
    ReasoningEffort,
)
from apix.config.base_config import PROVIDER_BASE_URL


class OpenaiChatBot(OpenAICompatibleChatBot):
    """A named OpenAI chat bot."""

    supports_developer_role = True
    reasoning_effort_map: ClassVar[dict[ReasoningEffort, str]] = {
        "low": "low",
        "medium": "medium",
        "high": "high",
    }
    disabled_reasoning_effort = "none"


class OpenaiProvider(OpenAICompatibleProvider[OpenaiChatBot]):
    """Create :class:`OpenaiChatBot` instances."""

    provider = "openai"
    api_key_env = "OPENAI_API_KEY"
    default_base_url = PROVIDER_BASE_URL.get(
        "openai",
        "https://api.openai.com/v1",
    )
    chat_bot_class = OpenaiChatBot
