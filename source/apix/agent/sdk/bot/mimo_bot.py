from apix.agent.sdk.bot.base import (
    MessageConfig,
    ModelCapabilities,
    ReasoningConfig,
)
from apix.agent.sdk.bot.base_bot import BaseOpenAIBot
from apix.config.base_config import PROVIDER_BASE_URL


class XiaomiMIMOBot(BaseOpenAIBot):
    """Xiaomi MiMo OpenAI-compatible Chat Completions adapter."""

    provider = "xiaomimimo"
    default_endpoint = PROVIDER_BASE_URL["xiaomimimo"]
    capabilities = ModelCapabilities(
        message_config=MessageConfig(
            supported_roles=("system", "user", "ai", "tool"),
        ),
        reasoning_config=ReasoningConfig(
            effort_path=None,
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
    )
