from dataclasses import dataclass
from typing import Any

from apix.agent.core.bot.base import FieldPath


@dataclass(frozen=True, slots=True)
class RequestField:
    path: FieldPath
    enabled: Any = True
    disabled: Any = False

    def __post_init__(self) -> None:
        if not self.path or any(
            not isinstance(key, str) or not key for key in self.path
        ):
            raise ValueError("request paths must contain non-empty string keys")
