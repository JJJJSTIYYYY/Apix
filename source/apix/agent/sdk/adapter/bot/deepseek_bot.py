from __future__ import annotations

from typing import Any

from apix.agent.sdk.adapter.bot.base import ModelCapabilities
from apix.agent.sdk.adapter.bot.base_bot import BaseOpenAIBot
from apix.config.base_config import PROVIDER_BASE_URL


class DeepSeekBot(BaseOpenAIBot):
    """DeepSeek Chat Completions adapter."""

    provider = "deepseek"
    capabilities = ModelCapabilities(
        supports_role=["system", "user", "ai", "tool"],
        supports_effort=["low", "high", "max"],
        reasoning_effort_map={
            "low": "low",
            "medium": "high",
            "high": "high",
        },
        require_reasoning_content=True,
        supports_name=True,
        supports_stream_usage=True,
    )

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        name: str = "assistant",
        role_definition: str = "",
        endpoint: str | None = None,
        capabilities: ModelCapabilities | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(
            model=model,
            name=name,
            role_definition=role_definition,
            endpoint=(
                endpoint
                if endpoint is not None
                else PROVIDER_BASE_URL["deepseek"]
            ),
            api_key=api_key,
            capabilities=capabilities,
            client=client,
        )

    def _provider_extra_body(
        self,
        extra_body: dict[str, Any],
        *,
        reasoning: bool,
    ) -> dict[str, Any]:
        body = dict(extra_body or {})
        body.setdefault(
            "thinking",
            {"type": "enabled" if reasoning else "disabled"},
        )
        return body
