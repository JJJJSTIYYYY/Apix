"""Shared types for OpenAI-compatible model adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ReasoningEffort = Literal["low", "medium", "high"]


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Provider capabilities that affect request serialization."""

    supports_developer_role: bool = False
    supports_reasoning_content: bool = False
    reasoning_effort_map: Mapping[ReasoningEffort, str] | None = None
    disabled_reasoning_effort: str | None = None
    thinking_switch: bool = False
