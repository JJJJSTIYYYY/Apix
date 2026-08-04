from apix.agent.sdk.adapter.bot.base import (
    MessageConfig,
    ModelCapabilities,
    ReasoningConfig,
    StreamConfig,
)
from apix.agent.sdk.adapter.bot.base_bot import BaseOpenAIBot
from apix.config.base_config import PROVIDER_BASE_URL


class DeepSeekBot(BaseOpenAIBot):
    """DeepSeek Chat Completions adapter."""

    provider = "deepseek"
    default_endpoint = PROVIDER_BASE_URL["deepseek"]
    capabilities = ModelCapabilities(
        message_config=MessageConfig(
            supported_roles=("system", "user", "ai", "tool"),
            include_name=True,
        ),
        reasoning_config=ReasoningConfig(
            supported_efforts=("low", "high", "max"),
            effort_map={
                "low": "low",
                "medium": "high",
                "high": "high",
            },
            enabled_extra_body={
                "thinking": {"type": "enabled"},
            },
            disabled_extra_body={
                "thinking": {"type": "disabled"},
            },
            history_field_map={
                "reasoning_content": ("reasoning",),
            },
        ),
        stream_config=StreamConfig(
            request_defaults={
                "stream_options": {"include_usage": True},
            },
        ),
    )
