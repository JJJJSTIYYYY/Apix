from dataclasses import dataclass, field
from typing import Any, Literal


MessageRole = Literal[
    "developer",
    "system",
    "user",
    "assistant",
    "tool",
]


@dataclass(slots=True)
class ApixMessageBase:

    role: MessageRole

    # Message content:
    # - str
    # - list[ContentPart]
    # - None (tool call only)
    content: str | list[dict[str, Any]] | None

    # Optional sender name
    name: str | None = None

    # Only used when role == "tool"
    tool_call_id: str | None = None

    # Unique message id
    id: str = ""

    # Generation id this message belongs to
    generation_id: str = ""

    # Conversation tree node id
    node_id: str = ""

    # Parent node id
    parent_id: str = ""

    # ISO8601 timestamp
    timestamp: str = ""

    # Arbitrary metadata
    info: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AiMessage(ApixMessageBase):

    role: Literal["assistant"] = "assistant"

    # Tool calls list
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    # Refusal content
    refusal: str | None = None

    # Reasoning content (not part of OpenAI message schema)
    reasoning: str | None = None


@dataclass(slots=True)
class AiMessageChunk(AiMessage):
    """
    Streaming assistant message chunk.
    """

    reasoning_chunk: str | None = None

    content_chunk: str | None = None

    tool_calls_chunk: list[dict[str, Any]] | None = None

    finish_reason: Literal[
        "stop",
        "length",
        "tool_calls",
        "content_filter",
        "unknow"
    ] | None = None

    def __add__(self, other: "AiMessageChunk") -> "AiMessageChunk":
        """
        Merge another chunk into this chunk.
        """
        if other.reasoning_chunk:
            self.reasoning_chunk = (self.reasoning_chunk or "") + other.reasoning_chunk

        if other.content_chunk:
            self.content_chunk = (self.content_chunk or "") + other.content_chunk

        if other.tool_calls_chunk:
            if self.tool_calls_chunk is None:
                self.tool_calls_chunk = []
            self.tool_calls_chunk.extend(other.tool_calls_chunk)

        if other.finish_reason is not None:
            self.finish_reason = other.finish_reason

        return self
    

@dataclass(slots=True)
class DeveloperMessage(ApixMessageBase):

    role: Literal["developer"] = "developer"

    content: str = ""


@dataclass(slots=True)
class SystemMessage(ApixMessageBase):

    role: Literal["system"] = "system"

    content: str = ""

    name: str | None = None


@dataclass(slots=True)
class ToolMessage(ApixMessageBase):

    role: Literal["tool"] = "tool"

    content: str = ""

    tool_call_id: str = ""


@dataclass(slots=True)
class UserMessage(ApixMessageBase):

    role: Literal["user"] = "user"

    # Compatible with text and multimodal content.
    content: str | list[dict[str, Any]] = ""


@dataclass(slots=True)
class InfoMessage(ApixMessageBase):

    role: Literal["info"] = "info"

    # Compatible with text and multimodal content.
    content: str | list[dict[str, Any]] = ""


AnyMessage = UserMessage | AiMessage | AiMessageChunk | ToolMessage | SystemMessage | InfoMessage | DeveloperMessage