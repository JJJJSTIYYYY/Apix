from __future__ import annotations

from typing import Any

from apix.agent.sdk.adapter.bot.base import ModelCapabilities
from apix.agent.sdk.adapter.bot.base_bot import BaseOpenAIBot
from apix.config.base_config import PROVIDER_BASE_URL


class XiaomiMIMOBot(BaseOpenAIBot):
    """Xiaomi MiMo OpenAI-compatible Chat Completions adapter."""

    provider = "xiaomimimo"
    capabilities = ModelCapabilities(
        supports_role=["system", "user", "ai", "tool"],
        supports_effort=[],
        reasoning_effort_map=None,
        require_reasoning_content=True,
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
                else PROVIDER_BASE_URL["xiaomimimo"]
            ),
            api_key=api_key,
            capabilities=capabilities,
            client=client,
        )

    def _reasoning_request(
        self,
        reasoning: bool,
        reasoning_effort: str,
    ) -> dict[str, Any]:
        return {}

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
