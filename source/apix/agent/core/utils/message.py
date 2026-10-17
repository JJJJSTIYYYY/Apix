"""OpenAI Chat messages with application identity, metadata and business extensions.

Protocol fields stay at the top level. ``info`` is a storage-only business event;
it is never sent to the model. Streaming uses my_llm.MessageStream directly.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar, Literal, TypeAlias
from uuid import uuid4

from openai.types.chat import ChatCompletionMessageFunctionToolCallParam

ToolCall: TypeAlias = ChatCompletionMessageFunctionToolCallParam
MessageRole = Literal["system", "developer", "user", "assistant", "tool"]
ContentPart: TypeAlias = dict[str, Any]
MessageContent: TypeAlias = str | list[ContentPart] | None


@dataclass(slots=True, kw_only=True)
class ApixMessageBase:
    role: ClassVar[MessageRole]
    content: MessageContent = None
    name: str | None = None
    message_uid: str = field(default_factory=lambda: uuid4().hex)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return an independent complete message, including application fields."""
        return {"role": self.role, **asdict(self)}

    def to_chat(self) -> dict[str, Any]:
        """Return Chat fields without application storage/context attributes."""
        values = self.to_dict()
        for key in ("message_uid", "metadata", "extensions"):
            values.pop(key)
        if self.role == "tool":
            values.pop("name", None)
        return {
            key: value for key, value in values.items()
            if value is not None or key == "content"
        }

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


@dataclass(slots=True, kw_only=True)
class ApixAiMessage(ApixMessageBase):
    role: ClassVar[Literal["assistant"]] = "assistant"
    tool_calls: list[ToolCall] = field(default_factory=list)
    refusal: str | None = None
    audio: dict[str, Any] | None = None
    annotations: list[dict[str, Any]] | None = None
    function_call: dict[str, Any] | None = None
    # Provider extension used by Chat-compatible reasoning models.
    reasoning_content: str | None = None

    @classmethod
    def from_chat(cls, message: dict[str, Any], **application_fields: Any) -> ApixAiMessage:
        """Attach application fields to a completed standard assistant message."""
        values = deepcopy(message)
        if values.pop("role", None) != "assistant":
            raise ValueError("expected an assistant Chat message")
        return cls(**values, **application_fields)


@dataclass(slots=True, kw_only=True)
class ApixSystemMessage(ApixMessageBase):
    role: ClassVar[Literal["system"]] = "system"
    content: str | list[ContentPart] = ""


@dataclass(slots=True, kw_only=True)
class ApixDeveloperMessage(ApixMessageBase):
    role: ClassVar[Literal["developer"]] = "developer"
    content: str | list[ContentPart] = ""


@dataclass(slots=True, kw_only=True)
class ApixToolMessage(ApixMessageBase):
    role: ClassVar[Literal["tool"]] = "tool"
    tool_call_id: str
    content: str | list[ContentPart] = ""

    def __post_init__(self) -> None:
        if not isinstance(self.tool_call_id, str) or not self.tool_call_id:
            raise ValueError("tool_call_id cannot be empty")


@dataclass(slots=True, kw_only=True)
class ApixUserMessage(ApixMessageBase):
    role: ClassVar[Literal["user"]] = "user"
    content: str | list[ContentPart] = ""


CompleteMessage: TypeAlias = (
    ApixUserMessage | ApixAiMessage | ApixToolMessage
    | ApixSystemMessage | ApixDeveloperMessage
)
AnyMessage: TypeAlias = CompleteMessage
