from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolProfile:
    supported: bool = True
    choice_modes: tuple[str, ...] = ("auto", "none", "required", "named")
    reasoning_choice_modes: tuple[str, ...] | None = None
    parallel: bool = True
