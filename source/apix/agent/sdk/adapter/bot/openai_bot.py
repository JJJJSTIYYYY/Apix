from apix.agent.sdk.adapter.bot.base import (
    MessageConfig,
    ModelCapabilities,
    ReasoningConfig,
    RequestConfig,
)
from apix.agent.sdk.adapter.bot.base_bot import BaseOpenAIBot
from apix.config.base_config import PROVIDER_BASE_URL


class OpenAIBot(BaseOpenAIBot):
    """OpenAI adapter using the Responses API."""

    provider = "openai"
    default_endpoint = PROVIDER_BASE_URL["openai"]
    capabilities = ModelCapabilities(
        request_config=RequestConfig(
            api_style="responses",
            request_defaults={"store": False},
        ),
        message_config=MessageConfig(
            supported_roles=(
                "developer",
                "system",
                "user",
                "ai",
                "tool",
            ),
        ),
        reasoning_config=ReasoningConfig(
            effort_path=("reasoning", "effort"),
            supported_efforts=(
                "none",
                "minimal",
                "low",
                "medium",
                "high",
                "xhigh",
                "max",
            ),
            effort_map={
                "low": "low",
                "medium": "medium",
                "high": "high",
            },
            disabled_effort="none",
        ),
    )
