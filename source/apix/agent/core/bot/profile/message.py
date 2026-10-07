from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MessageProfile:
    roles: tuple[str, ...] = ("system", "user", "assistant", "tool")
    supports_name: bool = False
