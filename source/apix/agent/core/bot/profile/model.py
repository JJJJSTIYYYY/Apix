from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from apix.agent.core.bot.base import ApiStyle
from apix.agent.core.bot.profile.message import MessageProfile
from apix.agent.core.bot.profile.reasoning import ReasoningProfile
from apix.agent.core.bot.profile.response import ResponseSchema
from apix.agent.core.bot.profile.tool import ToolProfile


@dataclass(frozen=True, slots=True)
class ModelProfile:
    pattern: str = "*"
    api_style: ApiStyle | None = None
    reasoning: ReasoningProfile = field(default_factory=ReasoningProfile)
    tools: ToolProfile = field(default_factory=ToolProfile)
    messages: MessageProfile | None = None
    response_schema: ResponseSchema | None = None
    request_options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CustomProfile:
    """Only explicitly supplied fields override the resolved model."""

    endpoint: str | None = None
    protocol: str | None = None
    api_style: ApiStyle | None = None
    model_profile: ModelProfile | None = None
    reasoning: ReasoningProfile | None = None
    tools: ToolProfile | None = None
    messages: MessageProfile | None = None
    response_schema: ResponseSchema | None = None
    request_options: Mapping[str, Any] | None = None
