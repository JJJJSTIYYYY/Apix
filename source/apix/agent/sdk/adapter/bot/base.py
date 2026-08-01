from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from apix.agent.sdk.utils.message import MessageRole


ReasoningEffort = Literal["low", "medium", "high"]
ProviderReasoningEffort = Literal[
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
]
ApiStyle = Literal["chat_completions", "responses", "ollama"]


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Provider capabilities adapter that affect request serialization."""

    supports_role: list[MessageRole] = field(default_factory=list)
    supports_effort: list[ProviderReasoningEffort] = field(
        default_factory=list
    )
    reasoning_effort_map: Mapping[ReasoningEffort, str] | None = None
    require_reasoning_content: bool = False
    require_reasoning_details: bool = False
    supports_reasoning: bool = True
    supports_tools: bool = True
    supports_name: bool = False
    supports_stream_usage: bool = False
    api_style: ApiStyle = "chat_completions"
