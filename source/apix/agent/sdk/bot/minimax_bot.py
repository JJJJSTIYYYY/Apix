from apix.agent.sdk.bot.base import (
    MessageConfig,
    ModelCapabilities,
    ReasoningConfig,
    StreamConfig,
)
from apix.agent.sdk.bot.base_bot import BaseOpenAIBot
from apix.config.base_config import PROVIDER_BASE_URL


class MiniMaxBot(BaseOpenAIBot):
    """MiniMax OpenAI-compatible Chat Completions adapter."""

    provider = "minimax"
    default_endpoint = PROVIDER_BASE_URL["minimax"]
    capabilities = ModelCapabilities(
        message_config=MessageConfig(
            supported_roles=("system", "user", "ai", "tool"),
        ),
        reasoning_config=ReasoningConfig(
            effort_path=None,
            extra_body_defaults={"reasoning_split": True},
            enabled_extra_body={
                "thinking": {"type": "adaptive"},
            },
            disabled_extra_body={
                "thinking": {"type": "disabled"},
            },
            history_field_map={
                "reasoning_content": ("reasoning",),
                "reasoning_details": ("extensions", "reasoning_details"),
            },
            stream_delta_mode="cumulative",
        ),
        stream_config=StreamConfig(
            request_defaults={
                "stream_options": {"include_usage": True},
            },
        ),
    )
