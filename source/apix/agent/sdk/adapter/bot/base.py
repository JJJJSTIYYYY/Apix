from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from apix.agent.sdk.utils.message import MessageRole


ReasoningEffort = Literal["low", "medium", "high"]


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Provider capabilities adapter that affect request serialization."""

    support_role: list[MessageRole] = []
    support_effort: list[ReasoningEffort | str] = []
    reasoning_effort_map: Mapping[ReasoningEffort, str] | None = None
    require_reasoning_content: bool = False
