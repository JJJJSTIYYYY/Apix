"""Shared public types for the profile-driven inference layer."""

from typing import Literal

ApiStyle = Literal[
    "chat_completions", "responses", "messages", "generate_content", "ollama_chat"
]
FieldPath = tuple[str | int, ...]
ReasoningEffort = str
StreamDeltaMode = Literal["incremental", "cumulative"]


class ProviderResponseError(RuntimeError):
    """A provider returned a failed response or an invalid stream."""
