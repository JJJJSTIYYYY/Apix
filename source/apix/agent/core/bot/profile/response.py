from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from apix.agent.core.bot.base import FieldPath


@dataclass(frozen=True, slots=True)
class ResponseField:
    path: FieldPath
    match: Mapping[str, Any] | None = None
    # A nested selector handles typed blocks inside typed output items.
    value: FieldPath | ResponseField = ()


@dataclass(frozen=True, slots=True)
class StreamField:
    event_path: FieldPath | None = None
    event_value: Any = None
    value_path: FieldPath = ()


Selector = FieldPath | ResponseField | StreamField


@dataclass(frozen=True, slots=True)
class ResponseLayout:
    content: Selector | None = None
    reasoning: Selector | None = None
    tool_calls: Selector | None = None
    usage: Selector | None = None
    finish_reason: Selector | None = None
    refusal: Selector | None = None
    extensions: Mapping[str, Selector] = field(default_factory=dict)
    extension_stream_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResponseSchema:
    complete: ResponseLayout = field(default_factory=ResponseLayout)
    stream: ResponseLayout = field(default_factory=ResponseLayout)


OPENAI_CHAT_SCHEMA = ResponseSchema(
    complete=ResponseLayout(
        content=("choices", 0, "message", "content"),
        reasoning=("choices", 0, "message", "reasoning_content"),
        tool_calls=("choices", 0, "message", "tool_calls"),
        usage=("usage",),
        finish_reason=("choices", 0, "finish_reason"),
        refusal=("choices", 0, "message", "refusal"),
    ),
    stream=ResponseLayout(
        content=("choices", 0, "delta", "content"),
        reasoning=("choices", 0, "delta", "reasoning_content"),
        tool_calls=("choices", 0, "delta", "tool_calls"),
        usage=("usage",),
        finish_reason=("choices", 0, "finish_reason"),
        refusal=("choices", 0, "delta", "refusal"),
    ),
)

OPENAI_RESPONSES_SCHEMA = ResponseSchema(
    complete=ResponseLayout(
        content=ResponseField(
            ("output",),
            {"type": "message"},
            ResponseField(("content",), {"type": "output_text"}, ("text",)),
        ),
        reasoning=ResponseField(
            ("output",),
            {"type": "reasoning"},
            ResponseField(("summary",), {"type": "summary_text"}, ("text",)),
        ),
        tool_calls=ResponseField(("output",), {"type": "function_call"}),
        refusal=ResponseField(
            ("output",),
            {"type": "message"},
            ResponseField(("content",), {"type": "refusal"}, ("refusal",)),
        ),
        usage=("usage",),
        finish_reason=("status",),
    ),
    stream=ResponseLayout(
        content=StreamField(("type",), "response.output_text.delta", ("delta",)),
        reasoning=StreamField(
            ("type",), "response.reasoning_summary_text.delta", ("delta",)
        ),
        refusal=StreamField(("type",), "response.refusal.delta", ("delta",)),
        usage=StreamField(("type",), "response.completed", ("response", "usage")),
    ),
)

ANTHROPIC_SCHEMA = ResponseSchema(
    complete=ResponseLayout(
        content=ResponseField(("content",), {"type": "text"}, ("text",)),
        reasoning=ResponseField(("content",), {"type": "thinking"}, ("thinking",)),
        tool_calls=ResponseField(("content",), {"type": "tool_use"}),
        usage=("usage",),
        finish_reason=("stop_reason",),
    ),
    stream=ResponseLayout(
        content=StreamField(("delta", "type"), "text_delta", ("delta", "text")),
        reasoning=StreamField(
            ("delta", "type"), "thinking_delta", ("delta", "thinking")
        ),
        finish_reason=StreamField(("type",), "message_delta", ("delta", "stop_reason")),
        usage=("usage",),
    ),
)

GEMINI_LAYOUT = ResponseLayout(
    content=ResponseField(
        ("candidates", 0, "content", "parts"), {"thought": False}, ("text",)
    ),
    reasoning=ResponseField(
        ("candidates", 0, "content", "parts"), {"thought": True}, ("text",)
    ),
    tool_calls=("candidates", 0, "content", "parts"),
    usage=("usageMetadata",),
    finish_reason=("candidates", 0, "finishReason"),
)
GEMINI_SCHEMA = ResponseSchema(complete=GEMINI_LAYOUT, stream=GEMINI_LAYOUT)
