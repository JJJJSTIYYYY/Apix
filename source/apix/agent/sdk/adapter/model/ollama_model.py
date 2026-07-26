"""Ollama OpenAI-compatible chat provider."""

from apix.agent.sdk.adapter.model.base_model import (
    OpenAICompatibleChatBot,
    OpenAICompatibleProvider,
)
from apix.config.base_config import PROVIDER_BASE_URL


def _default_ollama_base_url() -> str:
    base_url = PROVIDER_BASE_URL.get(
        "ollama:local",
        "http://localhost:11434",
    ).rstrip("/")
    return (
        base_url
        if base_url.endswith("/v1")
        else f"{base_url}/v1"
    )


class OllamaChatBot(OpenAICompatibleChatBot):
    """A named Ollama chat bot."""


class OllamaProvider(
    OpenAICompatibleProvider[OllamaChatBot]
):
    """Create :class:`OllamaChatBot` instances."""

    provider = "ollama"
    default_base_url = _default_ollama_base_url()
    chat_bot_class = OllamaChatBot
    local_api_key = "ollama"
