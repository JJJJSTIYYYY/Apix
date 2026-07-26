from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, TypeAlias, TypedDict
from uuid import uuid4

from apix.common.type import ChunkMergeError, IncompleteToolCallError


# ============================================================
# Types
# ============================================================

MessageRole = Literal[
    "developer",
    "system",
    "user",
    "ai",
    "tool",
    "info",
]

FinishReason = Literal[
    "stop",
    "length",
    "tool_calls",
    "content_filter",
    "unknown",
]

ContentPart: TypeAlias = dict[str, Any]
MessageContent: TypeAlias = str | list[ContentPart] | None


class ToolCall(TypedDict):
    """
    A completed tool call.

    args must already be decoded from the streamed JSON string.
    """

    call_id: str
    tool_name: str
    args: dict[str, Any] | None


# ============================================================
# Helpers
# ============================================================

def _new_message_id() -> str:
    return uuid4().hex


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Complete messages
# ============================================================

@dataclass(slots=True, kw_only=True)
class ApixMessageBase:
    """
    Base class for complete messages.

    role is supplied by subclasses and cannot be passed manually.
    """

    role: MessageRole = field(init=False)

    content: MessageContent = None
    name: str | None = None

    id: str = field(default_factory=_new_message_id)

    timestamp: str = field(default_factory=_utc_now_iso)

    info: dict[str, Any] = field(default_factory=dict) # Message information, usually contains name, token usage, duration and provider information.
    extra: dict[str, Any] = field(default_factory=dict) # Extra but important information, usually contains info such as raw tool calls for an ai message, upload files meta in user message and so on.


@dataclass(slots=True, kw_only=True)
class ApixAiMessage(ApixMessageBase):
    role: Literal["ai"] = field(
        default="ai",
        init=False,
    )

    content: MessageContent = None

    tool_calls: list[ToolCall] = field(default_factory=list)

    refusal: str | None = None
    reasoning: str | None = None

    finish_reason: FinishReason | None = None


@dataclass(slots=True, kw_only=True)
class ApixDeveloperMessage(ApixMessageBase):
    role: Literal["developer"] = field(
        default="developer",
        init=False,
    )

    content: str = ""


@dataclass(slots=True, kw_only=True)
class ApixSystemMessage(ApixMessageBase):
    role: Literal["system"] = field(
        default="system",
        init=False,
    )

    content: str = ""


@dataclass(slots=True, kw_only=True)
class ApixToolMessage(ApixMessageBase):
    role: Literal["tool"] = field(
        default="tool",
        init=False,
    )

    content: str = ""

    # Required for tool messages.
    tool_call_id: str

    def __post_init__(self) -> None:
        if not self.tool_call_id:
            raise ValueError("tool_call_id cannot be empty")


@dataclass(slots=True, kw_only=True)
class ApixUserMessage(ApixMessageBase):
    role: Literal["user"] = field(
        default="user",
        init=False,
    )

    content: str | list[ContentPart] = ""


# ============================================================
# Streaming tool-call delta
# ============================================================

@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallDelta:
    """
    Incremental data for one tool call.

    index identifies the tool call inside the assistant message.

    The *_delta fields are fragments, not complete values. For example:

        ToolCallDelta(
            index=0,
            call_id_delta="call_",
            tool_name_delta="get_",
            arguments_delta='{"city":',
        )

        ToolCallDelta(
            index=0,
            call_id_delta="123",
            tool_name_delta="weather",
            arguments_delta='"Tokyo"}',
        )

    After merging:

        call_id = "call_123"
        tool_name = "get_weather"
        arguments = '{"city":"Tokyo"}'
    """

    index: int

    call_id_delta: str = ""
    tool_name_delta: str = ""
    arguments_delta: str = ""

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("tool call index must be >= 0")

    def __add__(self, other: ToolCallDelta) -> ToolCallDelta:
        if not isinstance(other, ToolCallDelta):
            return NotImplemented

        if self.index != other.index:
            raise ChunkMergeError(
                "cannot merge tool call deltas with different indexes: "
                f"{self.index} != {other.index}"
            )

        return ToolCallDelta(
            index=self.index,
            call_id_delta=(
                self.call_id_delta
                + other.call_id_delta
            ),
            tool_name_delta=(
                self.tool_name_delta
                + other.tool_name_delta
            ),
            arguments_delta=(
                self.arguments_delta
                + other.arguments_delta
            ),
        )


# ============================================================
# Chunk merge helpers
# ============================================================

def _merge_identity(
    field_name: str,
    left: str,
    right: str,
) -> str:
    """
    Merge stream identity fields.

    Empty values mean that the provider did not include this field.
    Two non-empty values must be equal.
    """

    if left and right and left != right:
        raise ChunkMergeError(
            f"chunk {field_name} mismatch: "
            f"{left!r} != {right!r}"
        )

    return left or right


def _merge_optional_identity(
    field_name: str,
    left: str | None,
    right: str | None,
) -> str | None:
    if left and right and left != right:
        raise ChunkMergeError(
            f"chunk {field_name} mismatch: "
            f"{left!r} != {right!r}"
        )

    return left or right


def _merge_finish_reason(
    left: FinishReason | None,
    right: FinishReason | None,
) -> FinishReason | None:
    if (
        left is not None
        and right is not None
        and left != right
    ):
        raise ChunkMergeError(
            f"finish_reason mismatch: "
            f"{left!r} != {right!r}"
        )

    return right if right is not None else left


def _merge_tool_call_deltas(
    left: tuple[ToolCallDelta, ...],
    right: tuple[ToolCallDelta, ...],
) -> tuple[ToolCallDelta, ...]:
    """
    Merge tool-call deltas by index.

    This supports:

    - One tool call split across many chunks
    - Multiple parallel tool calls
    - Multiple deltas for the same index in one chunk
    - Interleaved tool-call chunks
    """

    merged: dict[int, ToolCallDelta] = {}

    for delta in (*left, *right):
        current = merged.get(delta.index)

        if current is None:
            merged[delta.index] = delta
        else:
            merged[delta.index] = current + delta

    return tuple(
        merged[index]
        for index in sorted(merged)
    )


# ============================================================
# Streaming assistant chunk
# ============================================================

@dataclass(frozen=True, slots=True, kw_only=True)
class ApixAiMessageChunk:
    """
    Streaming assistant-message delta.

    This class deliberately does not inherit ApixAiMessage.

    A chunk is not a complete message. Keeping it separate avoids having
    both `content` and `content_delta`, or both `tool_calls` and
    `tool_call_deltas`, on the same object.

    Addition is pure:

        merged = chunk1 + chunk2

    Neither chunk1 nor chunk2 is modified.
    """

    role: Literal["ai"] = field(
        default="ai",
        init=False,
    )

    content_delta: str = ""
    reasoning_delta: str = ""
    refusal_delta: str = ""

    tool_call_deltas: tuple[ToolCallDelta, ...] = ()

    finish_reason: FinishReason | None = None

    # Stream identity.
    #
    # These fields are intentionally empty by default. Giving each chunk a
    # generated ID would cause every chunk to appear to belong to a different
    # message.
    id: str = ""

    name: str | None = None

    # The first timestamp encountered is retained during aggregation.
    timestamp: str = ""

    info: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __add__(
        self,
        other: ApixAiMessageChunk,
    ) -> ApixAiMessageChunk:
        if not isinstance(other, ApixAiMessageChunk):
            return NotImplemented

        return ApixAiMessageChunk(
            content_delta=(
                self.content_delta
                + other.content_delta
            ),
            reasoning_delta=(
                self.reasoning_delta
                + other.reasoning_delta
            ),
            refusal_delta=(
                self.refusal_delta
                + other.refusal_delta
            ),
            tool_call_deltas=_merge_tool_call_deltas(
                self.tool_call_deltas,
                other.tool_call_deltas,
            ),
            finish_reason=_merge_finish_reason(
                self.finish_reason,
                other.finish_reason,
            ),
            id=_merge_identity(
                "id",
                self.id,
                other.id,
            ),
            name=_merge_optional_identity(
                "name",
                self.name,
                other.name,
            ),
            timestamp=(
                self.timestamp
                or other.timestamp
            ),
            # Metadata uses last-write-wins semantics.
            info={
                **self.info,
                **other.info,
            },
            extra={
                **self.extra,
                **other.extra,
            },
        )

    @property
    def is_finished(self) -> bool:
        return self.finish_reason is not None

    @property
    def has_delta(self) -> bool:
        return bool(
            self.content_delta
            or self.reasoning_delta
            or self.refusal_delta
            or self.tool_call_deltas
        )

    def to_message(
        self,
        *,
        require_finished: bool = False,
    ) -> ApixAiMessage:
        """
        Convert an aggregated chunk into a complete assistant message.

        Tool-call JSON is parsed only at this point. Parsing JSON during each
        chunk would fail because streamed JSON is normally incomplete.
        """

        if require_finished and not self.is_finished:
            raise ValueError(
                "cannot finalize an unfinished message stream"
            )

        tool_calls = tuple_delta_to_tool_calls(
            self.tool_call_deltas,
        )

        return ApixAiMessage(
            content=self.content_delta or None,
            name=self.name,
            id=self.id or _new_message_id(),
            timestamp=(
                self.timestamp
                or _utc_now_iso()
            ),
            info=dict(self.info),
            extra=dict(self.extra),
            tool_calls=tool_calls,
            refusal=self.refusal_delta or None,
            reasoning=self.reasoning_delta or None,
            finish_reason=self.finish_reason,
        )


def tuple_delta_to_tool_calls(
    deltas: tuple[ToolCallDelta, ...],
) -> list[ToolCall]:
    """
    Convert aggregated tool-call deltas into complete tool calls.
    """

    tool_calls: list[ToolCall] = []

    for delta in deltas:
        if not delta.call_id_delta:
            raise IncompleteToolCallError(
                f"tool call {delta.index} is missing call_id"
            )

        if not delta.tool_name_delta:
            raise IncompleteToolCallError(
                f"tool call {delta.index} is missing tool_name"
            )

        args: dict[str, Any] | None = None
        raw_args = delta.arguments_delta.strip()

        if raw_args:
            try:
                decoded_args = json.loads(raw_args)
            except json.JSONDecodeError as exc:
                raise IncompleteToolCallError(
                    f"tool call {delta.index} "
                    "contains invalid or incomplete JSON arguments"
                ) from exc

            if not isinstance(decoded_args, dict):
                raise IncompleteToolCallError(
                    f"tool call {delta.index} arguments "
                    "must decode to a JSON object"
                )

            args = decoded_args

        tool_calls.append(
            ToolCall(
                call_id=delta.call_id_delta,
                tool_name=delta.tool_name_delta,
                args=args,
            )
        )

    return tool_calls


# ============================================================
# Stateful accumulator
# ============================================================

@dataclass(slots=True)
class ApixAiMessageAccumulator:
    """
    Mutable stream accumulator.

    Chunk objects themselves remain immutable, while this class provides
    convenient stateful aggregation for async iteration.
    """

    _chunk: ApixAiMessageChunk = field(
        default_factory=ApixAiMessageChunk,
        init=False,
        repr=False,
    )

    def add(
        self,
        chunk: ApixAiMessageChunk,
    ) -> ApixAiMessageChunk:
        self._chunk = self._chunk + chunk
        return self._chunk

    @property
    def chunk(self) -> ApixAiMessageChunk:
        return self._chunk

    @property
    def is_finished(self) -> bool:
        return self._chunk.is_finished

    def to_message(
        self,
        *,
        require_finished: bool = False,
    ) -> ApixAiMessage:
        return self._chunk.to_message(
            require_finished=require_finished,
        )


# ============================================================
# Message unions
# ============================================================

CompleteMessage: TypeAlias = (
    ApixUserMessage
    | ApixAiMessage
    | ApixToolMessage
    | ApixSystemMessage
    | ApixDeveloperMessage
)

AnyMessage: TypeAlias = (
    CompleteMessage
    | ApixAiMessageChunk
)