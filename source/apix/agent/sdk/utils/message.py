"""Message objects and their storage representation.

Database-generated values such as the internal primary key and ``timestamp``
are deliberately absent from message objects.  A stored message contains the
following application-owned values::

    {
        "message_uid": str,
        "generation_id": str,
        "role": Literal["system", "user", "ai", "tool", "info"],
        "name": str | None,
        "content": str | list | None,
        "node_id": str,
        "parent_id": str,
        "metadata": {
            "duration": float,
            "model": str,
            "provider": str,
            "usage": dict,
        },
        "extensions": {
            "reasoning": str,
            "tool_calls": list[ToolCall],
            "tool_call_id": str,
            "uploaded_files": list[str],
            "active_file": str,
            "referenced_message": dict,
            "task": dict,
            "todo_list": list,
            "search_key_word": list[str],
            "search_urls": list[str],
        },
    }

``metadata`` is reserved for model/provider/usage and execution measurements.
``extensions`` carries business payloads.  Frequently used extension values
are exposed as properties below so callers do not need to manipulate the
dictionary directly.

For role `info`
- What is it?
> It is a branch of ai message which contains no think and no content.
> It just defines a dictionary struct, not a subclass of ApixMessageBase.
- When to use it?
> Use when you want to append some message information in append-only-database, but you can not modify an existing ai message.
> An ai message without think and content is not recommanded.
> Such as: use when a todo list is written, a web search tool is called by assistant and some website is visited.
info message does not provided a class, use ai_context_adapter.append_to_store(...) to store.
"""


from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, TypeAlias, TypedDict
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

def _new_message_uid() -> str:
    return uuid4().hex


# ============================================================
# Complete messages
# ============================================================

@dataclass(slots=True, kw_only=True)
class ApixMessageBase:
    """
    Base class for complete messages.

    ``role`` is supplied by subclasses and cannot be passed manually.
    """

    role: ClassVar[MessageRole]

    content: MessageContent = None
    name: str | None = None
    message_uid: str = field(default_factory=_new_message_uid)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    @property
    def uploaded_files(self) -> list[str]:
        value = self.extensions.get("uploaded_files")
        return value if isinstance(value, list) else []

    @uploaded_files.setter
    def uploaded_files(self, value: list[str]) -> None:
        self.extensions["uploaded_files"] = value

    @property
    def active_file(self) -> str | None:
        value = self.extensions.get("active_file")
        return value if isinstance(value, str) else None

    @active_file.setter
    def active_file(self, value: str | None) -> None:
        if value is None:
            self.extensions.pop("active_file", None)
        else:
            self.extensions["active_file"] = value

    @property
    def referenced_message(self) -> dict[str, Any] | None:
        value = self.extensions.get("referenced_message")
        return value if isinstance(value, dict) else None

    @referenced_message.setter
    def referenced_message(self, value: dict[str, Any] | None) -> None:
        if value is None:
            self.extensions.pop("referenced_message", None)
        else:
            self.extensions["referenced_message"] = value

    @property
    def task(self) -> dict[str, Any] | None:
        value = self.extensions.get("task")
        return value if isinstance(value, dict) else None

    @task.setter
    def task(self, value: dict[str, Any] | None) -> None:
        if value is None:
            self.extensions.pop("task", None)
        else:
            self.extensions["task"] = value

    @property
    def todo_list(self) -> list[dict[str, Any]]:
        value = self.extensions.get("todo_list")
        return value if isinstance(value, list) else []

    @todo_list.setter
    def todo_list(self, value: list[dict[str, Any]]) -> None:
        self.extensions["todo_list"] = value

    @property
    def system_instruction(self) -> list[str]:
        value = self.extensions.get("system_instruction")
        return value if isinstance(value, list) else []

    @system_instruction.setter
    def system_instruction(self, value: list[str]) -> None:
        self.extensions["system_instruction"] = value


class ApixAiMessage(ApixMessageBase):
    __slots__ = ()
    role: ClassVar[Literal["ai"]] = "ai"

    def __init__(
        self,
        *,
        content: MessageContent = None,
        name: str | None = None,
        message_uid: str | None = None,
        metadata: dict[str, Any] | None = None,
        extensions: dict[str, Any] | None = None,
        tool_calls: list[ToolCall] | None = None,
        refusal: str | None = None,
        reasoning: str | None = None,
        finish_reason: FinishReason | None = None,
    ) -> None:
        super().__init__(
            content=content,
            name=name,
            message_uid=message_uid or _new_message_uid(),
            metadata=dict(metadata or {}),
            extensions=dict(extensions or {}),
        )
        if tool_calls is not None:
            self.tool_calls = tool_calls
        if refusal is not None:
            self.refusal = refusal
        if reasoning is not None:
            self.reasoning = reasoning
        if finish_reason is not None:
            self.finish_reason = finish_reason

    @property
    def tool_calls(self) -> list[ToolCall]:
        value = self.extensions.get("tool_calls")
        return value if isinstance(value, list) else []

    @tool_calls.setter
    def tool_calls(self, value: list[ToolCall]) -> None:
        self.extensions["tool_calls"] = value

    @property
    def refusal(self) -> str | None:
        value = self.extensions.get("refusal")
        return value if isinstance(value, str) else None

    @refusal.setter
    def refusal(self, value: str | None) -> None:
        if value is None:
            self.extensions.pop("refusal", None)
        else:
            self.extensions["refusal"] = value

    @property
    def reasoning(self) -> str | None:
        value = self.extensions.get("reasoning")
        return value if isinstance(value, str) else None

    @reasoning.setter
    def reasoning(self, value: str | None) -> None:
        if value is None:
            self.extensions.pop("reasoning", None)
        else:
            self.extensions["reasoning"] = value

    @property
    def finish_reason(self) -> FinishReason | None:
        return self.metadata.get("finish_reason")

    @finish_reason.setter
    def finish_reason(self, value: FinishReason | None) -> None:
        if value is None:
            self.metadata.pop("finish_reason", None)
        else:
            self.metadata["finish_reason"] = value


@dataclass(slots=True, kw_only=True)
class ApixDeveloperMessage(ApixMessageBase):
    role: ClassVar[Literal["developer"]] = "developer"

    content: str = ""


@dataclass(slots=True, kw_only=True)
class ApixSystemMessage(ApixMessageBase):
    role: ClassVar[Literal["system"]] = "system"

    content: str = ""


class ApixToolMessage(ApixMessageBase):
    __slots__ = ()
    role: ClassVar[Literal["tool"]] = "tool"

    def __init__(
        self,
        *,
        tool_call_id: str | None = None,
        content: str = "",
        name: str | None = None,
        message_uid: str | None = None,
        metadata: dict[str, Any] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            content=content,
            name=name,
            message_uid=message_uid or _new_message_uid(),
            metadata=dict(metadata or {}),
            extensions=dict(extensions or {}),
        )
        if tool_call_id is not None:
            self.tool_call_id = tool_call_id
        if not self.tool_call_id:
            raise ValueError("tool_call_id cannot be empty")

    @property
    def tool_call_id(self) -> str | None:
        value = self.extensions.get("tool_call_id")
        return value if isinstance(value, str) else None

    @tool_call_id.setter
    def tool_call_id(self, value: str | None) -> None:
        if value is None:
            self.extensions.pop("tool_call_id", None)
        else:
            self.extensions["tool_call_id"] = value


@dataclass(slots=True, kw_only=True)
class ApixUserMessage(ApixMessageBase):
    role: ClassVar[Literal["user"]] = "user"

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

    role: ClassVar[Literal["ai"]] = "ai"

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
    message_uid: str = ""

    name: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

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
            message_uid=_merge_identity(
                "message_uid",
                self.message_uid,
                other.message_uid,
            ),
            name=_merge_optional_identity(
                "name",
                self.name,
                other.name,
            ),
            # Metadata and extensions uses last-write-wins semantics.
            metadata={
                **self.metadata,
                **other.metadata,
            },
            extensions={
                **self.extensions,
                **other.extensions,
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
            message_uid=self.message_uid or _new_message_uid(),
            metadata=dict(self.metadata),
            extensions=dict(self.extensions),
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
