from typing import TYPE_CHECKING

from apix.agent.core.bot.base_bot import BaseOpenAIBot

if TYPE_CHECKING:
    from apix.agent.store.utils.llm_provider_helper import get_custom_provider_meta


class CustomBot(BaseOpenAIBot):
    """OpenAI-compatible inference with an explicit endpoint and optional profile."""

    provider = "custom"


def __getattr__(name):
    if name == "get_custom_provider_meta":
        from apix.agent.store.utils.llm_provider_helper import get_custom_provider_meta

        return get_custom_provider_meta
    raise AttributeError(name)


__all__ = ["CustomBot", "get_custom_provider_meta"]
