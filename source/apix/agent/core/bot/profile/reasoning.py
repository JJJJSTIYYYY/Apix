from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from apix.agent.core.bot.profile.base import RequestField
from apix.agent.core.bot.profile.response import ResponseField, StreamField


@dataclass(frozen=True, slots=True)
class ReasoningProfile:
    mode: Literal["none", "optional", "always"] = "none"
    effort_values: tuple[str, ...] = ()
    effort_map: Mapping[str, str] = field(default_factory=dict)
    toggle: RequestField | None = None
    effort: RequestField | None = None
    output: ResponseField | None = None
    stream_output: ResponseField | StreamField | None = None
    replay: Literal["never", "always", "when_tools"] = "never"
    stream_mode: Literal["incremental", "cumulative"] = "incremental"
    stream_only: bool = False
    effort_without_reasoning: bool = False

    def __post_init__(self) -> None:
        if self.mode not in ("none", "optional", "always"):
            raise ValueError("invalid reasoning mode")
        if self.replay not in ("never", "always", "when_tools"):
            raise ValueError("invalid reasoning replay policy")
        if self.stream_mode not in ("incremental", "cumulative"):
            raise ValueError("invalid reasoning stream mode")
        if any(value not in self.effort_values for value in self.effort_map.values()):
            raise ValueError("effort aliases must map to declared effort values")

    def should_replay(self, has_tools: bool) -> bool:
        return self.replay == "always" or (self.replay == "when_tools" and has_tools)
