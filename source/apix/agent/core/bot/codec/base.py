from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from apix.agent.core.bot.base import FieldPath, ProviderResponseError
from apix.agent.core.bot.profile import ModelProfile, ResponseField, StreamField
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixAiMessageChunk,
    ApixMessageBase,
)


def read(value: Any, key: str | int, default: Any = None) -> Any:
    if isinstance(key, int):
        return (
            value[key]
            if isinstance(value, (list, tuple)) and 0 <= key < len(value)
            else default
        )
    return (
        value.get(key, default)
        if isinstance(value, Mapping)
        else getattr(value, key, default)
    )


def read_path(value: Any, path: FieldPath) -> Any:
    for key in path:
        value = read(value, key)
        if value is None:
            break
    return value


def dump(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dump(item) for item in value]
    if callable(getattr(value, "model_dump", None)):
        return dump(value.model_dump(exclude_none=True))
    if callable(getattr(value, "to_dict", None)):
        return dump(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            key: dump(item)
            for key, item in vars(value).items()
            if not key.startswith("_") and item is not None
        }
    return deepcopy(value)


def select(value: Any, selector: Any) -> Any:
    if selector is None:
        return None
    if isinstance(selector, StreamField):
        if (
            selector.event_path is not None
            and read_path(value, selector.event_path) != selector.event_value
        ):
            return None
        return read_path(value, selector.value_path)
    if isinstance(selector, ResponseField):
        result = read_path(value, selector.path)
        if selector.match is not None or selector.value:
            items = result if isinstance(result, (list, tuple)) else []
            result = []
            for item in items:
                if selector.match is not None and any(
                    read(item, key, False if expected is False else None) != expected
                    for key, expected in selector.match.items()
                ):
                    continue
                projected = select(item, selector.value) if selector.value else item
                if isinstance(projected, list):
                    result.extend(projected)
                elif projected is not None:
                    result.append(projected)
        return result
    return read_path(value, selector)


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "".join(text(item) for item in value)
    raise TypeError("a text selector must resolve to text")


def arguments(value: Any) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    if not isinstance(value, str):
        raise TypeError("tool arguments must be a JSON object or string")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("tool arguments contain invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise TypeError("tool arguments must decode to a JSON object")
    return decoded


def json_arguments(value: Any) -> str:
    return (
        value
        if isinstance(value, str)
        else json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))
    )


def finish_reason(value: Any) -> str | None:
    if value is None:
        return None
    return {
        "stop": "stop",
        "end_turn": "stop",
        "stop_sequence": "stop",
        "STOP": "stop",
        "completed": "stop",
        "length": "length",
        "max_tokens": "length",
        "max_output_tokens": "length",
        "MAX_TOKENS": "length",
        "tool_calls": "tool_calls",
        "tool_use": "tool_calls",
        "content_filter": "content_filter",
        "SAFETY": "content_filter",
        "refusal": "content_filter",
    }.get(str(value), "unknown")


@dataclass(slots=True)
class StreamState:
    message_uid: str = field(default_factory=lambda: uuid4().hex)
    reasoning_snapshot: str = ""
    saw_tools: bool = False
    finished: bool = False
    data: dict[str, Any] = field(default_factory=dict)


class BaseCodec(ABC):
    def __init__(self, profile: ModelProfile) -> None:
        self.profile = profile
        self.schema = profile.response_schema

    def validate_message(self, message: ApixMessageBase) -> None:
        if not isinstance(message, ApixMessageBase):
            raise TypeError("message must be a complete ApixMessageBase instance")
        if message.role not in self.profile.messages.roles:
            raise ValueError(
                f"message role {message.role!r} is not supported by this model"
            )

    def encode_messages(
        self, messages: list[ApixMessageBase], *, has_tools: bool | None = None
    ) -> list[dict[str, Any]]:
        result = []
        for message in messages:
            self.validate_message(message)
            encoded = self.encode_message(message, has_tools=has_tools)
            result.extend(encoded if isinstance(encoded, list) else [encoded])
        return result

    @abstractmethod
    def encode_message(
        self, message: ApixMessageBase, *, has_tools: bool | None = None
    ) -> dict | list[dict]: ...

    def replay_reasoning(self, message: ApixAiMessage, has_tools: bool | None) -> bool:
        return self.profile.reasoning.should_replay(
            bool(message.tool_calls) if has_tools is None else has_tools
        )

    @abstractmethod
    def encode_request(
        self,
        messages: list[ApixMessageBase],
        tools: list[dict],
        tool_choice: str | None,
        parallel: bool | None,
    ) -> dict: ...

    @abstractmethod
    def decode_response(self, response: Any, **context: Any) -> ApixAiMessage: ...

    @abstractmethod
    def decode_stream(
        self, event: Any, state: StreamState, **context: Any
    ) -> ApixAiMessageChunk: ...

    def decode_usage(self, value: Any) -> dict[str, Any]:
        value = dump(value)
        if not isinstance(value, dict):
            return {}
        result = {}
        for target, sources in {
            "input_tokens": ("input_tokens", "prompt_tokens", "promptTokenCount"),
            "output_tokens": (
                "output_tokens",
                "completion_tokens",
                "candidatesTokenCount",
            ),
            "total_tokens": ("total_tokens", "totalTokenCount"),
        }.items():
            for source in sources:
                if source in value:
                    result[target] = value[source]
                    break
        if "input_tokens" in value:
            result["input_tokens"] += value.get(
                "cache_creation_input_tokens", 0
            ) + value.get("cache_read_input_tokens", 0)
        if "candidatesTokenCount" in value:
            result["output_tokens"] += value.get("thoughtsTokenCount", 0)
        if "total_tokens" not in result and result:
            result["total_tokens"] = result.get("input_tokens", 0) + result.get(
                "output_tokens", 0
            )
        for key in (
            "input_tokens_details",
            "output_tokens_details",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            if key in value:
                result[key] = value[key]
        return result

    def metadata(
        self,
        response: Any,
        *,
        provider: str,
        model: str,
        duration: float | None = None,
        usage: Any = None,
        **_: Any,
    ) -> dict:
        result = {"provider": provider, "model": read(response, "model") or model}
        if read(response, "id"):
            result["id"] = read(response, "id")
        if duration is not None:
            result["duration"] = duration
        normalized = self.decode_usage(usage)
        if normalized:
            result["usage"] = normalized
        return result

    def values(self, response: Any, *, stream: bool = False) -> dict:
        layout = self.schema.stream if stream else self.schema.complete
        values = {
            key: select(response, getattr(layout, key))
            for key in (
                "content",
                "reasoning",
                "tool_calls",
                "usage",
                "finish_reason",
                "refusal",
            )
        }
        override = (
            self.profile.reasoning.stream_output
            if stream
            else self.profile.reasoning.output
        )
        if override is not None:
            values["reasoning"] = select(response, override)
        values["extensions"] = {
            key: dump(selected)
            for key, selector in layout.extensions.items()
            if (selected := select(response, selector)) is not None
        }
        return values

    def chunk(
        self,
        state: StreamState,
        *,
        content: str = "",
        reasoning: str = "",
        refusal: str = "",
        tools: tuple = (),
        finish: str | None = None,
        metadata: dict | None = None,
        extensions: dict | None = None,
        name: str = "assistant",
    ) -> ApixAiMessageChunk:
        extensions = deepcopy(extensions or {})
        for key, delta_fields in self.schema.stream.extension_stream_fields.items():
            if key not in extensions:
                continue
            retained = state.data.setdefault("extension_blocks", {}).setdefault(key, {})
            items = extensions[key]
            if not isinstance(items, list):
                raise ProviderResponseError("streaming extension blocks must be a list")
            for item in items:
                if not isinstance(item, dict):
                    raise ProviderResponseError(
                        "streaming extension block must be an object"
                    )
                index = item.get("index")
                if index is not None and (type(index) is not int or index < 0):
                    raise ProviderResponseError(
                        "extension block index must be a nonnegative integer"
                    )
                if item.get("id") is not None and not isinstance(item["id"], str):
                    raise ProviderResponseError("extension block id must be a string")
                identity = (
                    ("index", index)
                    if index is not None
                    else ("id", item["id"])
                    if item.get("id")
                    else ("position", len(retained))
                )
                block = retained.setdefault(identity, {})
                for key_name, value in item.items():
                    if (
                        key_name in ("type", "id", "format")
                        and block.get(key_name) is not None
                        and value is not None
                        and block[key_name] != value
                    ):
                        raise ProviderResponseError(
                            "streaming extension block identity changed"
                        )
                    if key_name in delta_fields and value is not None:
                        if not isinstance(value, str):
                            raise ProviderResponseError(
                                "extension text delta must be a string"
                            )
                        block[key_name] = (block.get(key_name) or "") + value
                    elif value is not None or key_name not in block:
                        block[key_name] = deepcopy(value)
            extensions[key] = deepcopy(list(retained.values()))
        if reasoning and self.profile.reasoning.stream_mode == "cumulative":
            if not reasoning.startswith(state.reasoning_snapshot):
                raise ProviderResponseError(
                    "cumulative reasoning changed an already emitted prefix"
                )
            snapshot = reasoning
            reasoning = snapshot[len(state.reasoning_snapshot) :]
            state.reasoning_snapshot = snapshot
        state.saw_tools = state.saw_tools or bool(tools)
        if finish == "stop" and state.saw_tools:
            finish = "tool_calls"
        if finish is not None:
            state.finished = True
        metadata = dict(metadata or {})
        if finish:
            metadata["finish_reason"] = finish
        return ApixAiMessageChunk(
            content_delta=content,
            reasoning_delta=reasoning,
            refusal_delta=refusal,
            tool_call_deltas=tools,
            finish_reason=finish,
            message_uid=state.message_uid,
            metadata=metadata,
            extensions=extensions,
            name=name,
        )


def function_schemas(schemas: list[dict]) -> list[dict]:
    functions = []
    for schema in schemas:
        if schema.get("type") != "function" or not isinstance(
            schema.get("function"), Mapping
        ):
            raise ValueError("only Apix-managed function tools are allowed")
        function = schema["function"]
        if not isinstance(function.get("name"), str) or not function["name"]:
            raise ValueError("function tools require a name")
        functions.append(deepcopy(dict(function)))
    return functions
