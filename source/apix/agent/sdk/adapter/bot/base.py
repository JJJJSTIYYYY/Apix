from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

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
ApiStyle = Literal["chat_completions", "responses"]
StreamDeltaMode = Literal["incremental", "cumulative"]
FieldPath = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RequestConfig:
    """Provider request protocol and provider-neutral request defaults."""

    # OpenAI SDK resource used to submit requests.
    api_style: ApiStyle = "chat_completions"

    # Top-level SDK parameters included in every request.
    request_defaults: Mapping[str, Any] = field(default_factory=dict)

    # Raw provider extensions forwarded through the SDK's ``extra_body``.
    extra_body_defaults: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MessageConfig:
    """Provider rules for serializing conversation messages."""

    # APIX roles accepted by the provider; an empty tuple accepts every role.
    supported_roles: tuple[MessageRole, ...] = ()

    # Whether the provider accepts the optional message ``name`` field.
    include_name: bool = False


@dataclass(frozen=True, slots=True)
class ReasoningConfig:
    """Provider reasoning controls, history, and stream semantics."""

    # Whether reasoning-related request and response handling is enabled.
    supported: bool = True

    # Nested request path receiving the mapped effort value. ``None`` omits it.
    effort_path: FieldPath | None = ("reasoning_effort",)

    # Effort values accepted by the provider after mapping.
    supported_efforts: tuple[ProviderReasoningEffort, ...] = ()

    # Mapping from APIX's portable effort levels to provider effort values.
    effort_map: Mapping[ReasoningEffort, str] = field(default_factory=dict)

    # Effort value sent when callers disable reasoning; ``None`` omits it.
    disabled_effort: ProviderReasoningEffort | None = None

    # Reasoning-related top-level request defaults merged before effort.
    request_defaults: Mapping[str, Any] = field(default_factory=dict)

    # Reasoning-related raw body fields included in every reasoning request.
    extra_body_defaults: Mapping[str, Any] = field(default_factory=dict)

    # Raw body defaults added when callers enable reasoning.
    enabled_extra_body: Mapping[str, Any] = field(default_factory=dict)

    # Raw body defaults added when callers disable reasoning.
    disabled_extra_body: Mapping[str, Any] = field(default_factory=dict)

    # Maps provider history fields to paths on an ``ApixAiMessage``.
    history_field_map: Mapping[str, FieldPath] = field(default_factory=dict)

    # Whether streamed reasoning text is incremental or cumulative.
    stream_delta_mode: StreamDeltaMode = "incremental"


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Provider tool-calling capabilities."""

    # Whether bound function schemas may be included in requests.
    supported: bool = True


@dataclass(frozen=True, slots=True)
class StreamConfig:
    """Provider options that only apply to streaming requests."""

    # Top-level SDK parameters merged only when ``stream=True``.
    request_defaults: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Grouped declarative differences between model provider protocols.

    OpenAI-compatible provider classes should normally only choose an
    endpoint and configure this object.  The shared bot implementation reads
    the nested groups to build requests, serialize history, parse streams,
    and enable optional features without provider-specific method overrides.
    """

    # Request resource, global request defaults, and raw provider extensions.
    request_config: RequestConfig = field(default_factory=RequestConfig)

    # Supported roles and optional message-name behavior.
    message_config: MessageConfig = field(default_factory=MessageConfig)

    # Reasoning effort, provider switches, history, and stream behavior.
    reasoning_config: ReasoningConfig = field(default_factory=ReasoningConfig)

    # Function-calling availability.
    tool_config: ToolConfig = field(default_factory=ToolConfig)

    # Parameters that should only be sent for streaming requests.
    stream_config: StreamConfig = field(default_factory=StreamConfig)
