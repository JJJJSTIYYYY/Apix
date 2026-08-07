from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable, Mapping
from copy import deepcopy
from dataclasses import replace
import json
from time import perf_counter
from typing import Any, Self
from uuid import uuid4


from apix.agent.sdk.adapter.bot.base import (
    MessageConfig,
    ModelCapabilities,
    ReasoningConfig,
    ReasoningEffort,
)
from apix.agent.sdk.tool import Tool, ToolNode
from apix.agent.sdk.utils.context import RoleSchema, to_prompt
from apix.agent.sdk.utils.message import (
    AnyMessage,
    ApixAiMessage,
    ApixAiMessageChunk,
    ApixMessageBase,
    ApixSystemMessage,
    ApixToolMessage,
    ToolCall,
    ToolCallDelta,
)
from apix.config.base_config import LLM_MAX_RETRY, LLM_TIMEOUT


def _read(value: Any, key: str, default: Any = None) -> Any:
    """Read an attribute from SDK objects or a key from test dictionaries."""
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _model_dump(value: Any) -> Any:
    """Convert SDK/Pydantic values to JSON-compatible Python values."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _model_dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_model_dump(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(exclude_none=True)

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    data = getattr(value, "__dict__", None)
    if isinstance(data, dict):
        return {
            key: _model_dump(item)
            for key, item in data.items()
            if not key.startswith("_") and item is not None
        }
    return value


def _merge_mappings(*mappings: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-merge mappings while isolating all retained values."""
    merged: dict[str, Any] = {}
    for mapping in mappings:
        for key, value in mapping.items():
            previous = merged.get(key)
            if isinstance(previous, Mapping) and isinstance(value, Mapping):
                merged[key] = _merge_mappings(previous, value)
            else:
                merged[key] = deepcopy(value)
    return merged


def _set_path(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    """Set a value at a nested request path, preserving sibling values."""
    current = target
    for key in path[:-1]:
        child = current.get(key)
        if isinstance(child, Mapping):
            nested = deepcopy(dict(child))
        else:
            nested = {}
        current[key] = nested
        current = nested
    current[path[-1]] = deepcopy(value)


def _read_path(value: Any, path: tuple[str, ...]) -> Any:
    """Read a mixed attribute/mapping path from an APIX message."""
    current = value
    for key in path:
        current = _read(current, key)
        if current is None:
            return None
    return current


class BaseBot(ABC):
    """Provider-neutral LLM wrapper.

    A bot only serializes requests and responses for one model provider. It
    deliberately owns no agent state, graph loop, tool execution, or memory.
    """

    provider = "base"
    capabilities = ModelCapabilities()

    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        api_key: str,
        capabilities: ModelCapabilities | None = None,
        role_schema: RoleSchema | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must be a non-empty string")
        if not isinstance(api_key, str):
            raise TypeError("api_key must be a string")
        if capabilities is not None and not isinstance(
            capabilities, ModelCapabilities
        ):
            raise TypeError("capabilities must be a ModelCapabilities object")

        self.model = model.strip()
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        if capabilities is not None:
            self.capabilities = capabilities
        self.role_schema: RoleSchema | None = None
        if role_schema is not None:
            self.bind_role_schema(role_schema)
        self._tool_schemas: list[dict[str, Any]] = []

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        """Return an isolated copy of the currently bound tool schemas."""
        return deepcopy(self._tool_schemas)

    def bind_role_schema(self, role_schema: RoleSchema) -> Self:
        """Bind a role schema to the bot instance."""
        if (
            not isinstance(role_schema, dict)
            or not isinstance(role_schema.get("name"), str)
            or not role_schema["name"].strip()
            or not isinstance(role_schema.get("definition"), str)
            or (
                role_schema.get("title") is not None
                and not isinstance(role_schema.get("title"), str)
            )
        ):
            raise TypeError("role_schema must be a RoleSchema object")

        self.role_schema = deepcopy(role_schema)
        return self

    @property
    def name(self) -> str:
        """Return the bound role name or the default assistant name."""
        if self.role_schema is None:
            return "assistant"
        return self.role_schema["name"].strip()

    def bind_tools(
        self,
        tool_set: Iterable[Tool] | ToolNode,
        tool_permission_set: set[str] | None = None,
    ) -> Self:
        """Replace the tools bound to subsequent invoke and stream calls."""
        if isinstance(tool_set, ToolNode):
            schemas = tool_set.get_schemas(filter_names=tool_permission_set)
        else:
            if isinstance(tool_set, (str, bytes)):
                raise TypeError(
                    "tool_set must be an iterable of Tool objects or ToolNode"
                )
            try:
                tools = list(tool_set)
            except TypeError as exc:
                raise TypeError(
                    "tool_set must be an iterable of Tool objects or ToolNode"
                ) from exc

            invalid = next(
                (tool for tool in tools if not isinstance(tool, Tool)),
                None,
            )
            if invalid is not None:
                raise TypeError(
                    "tool_set must contain only Tool objects, "
                    f"got {type(invalid).__name__}"
                )
            schemas = [tool.get_schema() for tool in tools]

        self._tool_schemas = deepcopy(schemas)
        return self

    def _ordered_messages(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
    ) -> list[AnyMessage]:
        if not isinstance(messages, list):
            raise TypeError("messages must be a list")
        if system_prompt is not None and not isinstance(system_prompt, list):
            raise TypeError("system_prompt must be a list or None")

        ordered = list(system_prompt or [])
        if self.role_schema:
            ordered.append(
                ApixSystemMessage(content=to_prompt(self.role_schema, "RoleSchema"))
            )
        ordered.extend(messages)
        return ordered

    def _supports_role(self, role: str) -> bool:
        supported = self.capabilities.message_config.supported_roles
        return not supported or role in supported

    @staticmethod
    def _chat_tool_call(tool_call: ToolCall) -> dict[str, Any]:
        arguments = json.dumps(
            tool_call.get("args") or {},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return {
            "id": tool_call["call_id"],
            "type": "function",
            "function": {
                "name": tool_call["tool_name"],
                "arguments": arguments,
            },
        }

    def convert_message_for_api(
        self,
        message: ApixMessageBase,
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Serialize one APIX message to Chat Completions format."""
        if not isinstance(message, ApixMessageBase):
            raise TypeError(
                "message must be a complete ApixMessageBase instance"
            )
        if not self._supports_role(message.role):
            return None

        api_role = "assistant" if message.role == "ai" else message.role
        content = message.content
        if api_role in {"assistant", "tool"} and content is None:
            content = ""

        result: dict[str, Any] = {"role": api_role, "content": content}
        if self.capabilities.message_config.include_name and message.name:
            result["name"] = message.name

        if isinstance(message, ApixAiMessage):
            if message.tool_calls:
                result["tool_calls"] = [
                    self._chat_tool_call(tool_call)
                    for tool_call in message.tool_calls
                ]
            history_fields = (
                self.capabilities.reasoning_config.history_field_map
            )
            for api_field, source_path in history_fields.items():
                value = _read_path(message, source_path)
                if value is not None:
                    result[api_field] = deepcopy(value)

        if isinstance(message, ApixToolMessage):
            result["tool_call_id"] = message.tool_call_id
        return result

    def _prepare_api_messages(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
    ) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for message in self._ordered_messages(messages, system_prompt):
            converted = self.convert_message_for_api(message)
            if converted is None:
                continue
            if isinstance(converted, list):
                serialized.extend(converted)
            else:
                serialized.append(converted)
        return serialized

    @staticmethod
    def _normalize_finish_reason(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value)
        if normalized in {
            "stop",
            "length",
            "tool_calls",
            "content_filter",
        }:
            return normalized
        if normalized in {"max_tokens", "max_output_tokens"}:
            return "length"
        return "unknown"

    @staticmethod
    def _parse_tool_arguments(value: Any) -> dict[str, Any] | None:
        if value is None or value == "":
            return None
        if isinstance(value, Mapping):
            return dict(value)
        if not isinstance(value, str):
            raise TypeError("tool arguments must be a JSON object or string")

        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("tool arguments contain invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("tool arguments must decode to a JSON object")
        return decoded

    @classmethod
    def _chat_tool_calls(cls, value: Any) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for index, item in enumerate(value or []):
            function = _read(item, "function", {})
            call_id = _read(item, "id") or f"call_{uuid4().hex}"
            name = _read(function, "name")
            if not name:
                raise ValueError(f"tool call {index} has no function name")
            calls.append(
                ToolCall(
                    call_id=str(call_id),
                    tool_name=str(name),
                    args=cls._parse_tool_arguments(
                        _read(function, "arguments")
                    ),
                )
            )
        return calls

    @staticmethod
    def _chat_tool_call_deltas(value: Any) -> tuple[ToolCallDelta, ...]:
        deltas: list[ToolCallDelta] = []
        for fallback_index, item in enumerate(value or []):
            function = _read(item, "function", {})
            index = _read(item, "index", fallback_index)
            arguments = _read(function, "arguments", "")
            if isinstance(arguments, Mapping):
                arguments = json.dumps(
                    dict(arguments),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            deltas.append(
                ToolCallDelta(
                    index=int(index),
                    call_id_delta=str(_read(item, "id", "") or ""),
                    tool_name_delta=str(
                        _read(function, "name", "") or ""
                    ),
                    arguments_delta=str(arguments or ""),
                )
            )
        return tuple(deltas)

    @staticmethod
    def _reasoning_from_message(message: Any) -> str:
        for key in ("reasoning_content", "reasoning", "thinking"):
            value = _read(message, key)
            if isinstance(value, str) and value:
                return value

        details = _read(message, "reasoning_details")
        if isinstance(details, list):
            return "".join(
                str(_read(item, "text", "") or "") for item in details
            )
        return ""

    def _metadata(
        self,
        response: Any,
        *,
        duration: float | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "provider": self.provider,
            "model": _read(response, "model", self.model) or self.model,
        }
        response_id = _read(response, "id")
        if response_id:
            metadata["id"] = response_id
        usage = _model_dump(_read(response, "usage"))
        if isinstance(usage, dict) and usage:
            metadata["usage"] = usage
        if duration is not None:
            metadata["duration"] = duration
        return metadata

    def convert_message_to_apix(
        self,
        response: Any,
        *,
        stream: bool = False,
        message_uid: str | None = None,
        duration: float | None = None,
    ) -> ApixAiMessage | ApixAiMessageChunk:
        """Convert a Chat Completions response into APIX messages."""
        choices = _read(response, "choices") or []
        choice = choices[0] if choices else None
        metadata = self._metadata(response, duration=duration)

        if stream:
            delta = _read(choice, "delta", {}) if choice is not None else {}
            finish_reason = self._normalize_finish_reason(
                _read(choice, "finish_reason") if choice is not None else None
            )
            if finish_reason is not None:
                metadata["finish_reason"] = finish_reason
            return ApixAiMessageChunk(
                content_delta=str(_read(delta, "content", "") or ""),
                reasoning_delta=self._reasoning_from_message(delta),
                refusal_delta=str(_read(delta, "refusal", "") or ""),
                tool_call_deltas=self._chat_tool_call_deltas(
                    _read(delta, "tool_calls")
                ),
                finish_reason=finish_reason,
                message_uid=message_uid or uuid4().hex,
                name=self.name,
                metadata=metadata,
            )

        if choice is None:
            raise ValueError("chat completion response contains no choices")
        message = _read(choice, "message", {})
        finish_reason = self._normalize_finish_reason(
            _read(choice, "finish_reason")
        )
        if finish_reason is not None:
            metadata["finish_reason"] = finish_reason

        extensions: dict[str, Any] = {}
        details = _model_dump(_read(message, "reasoning_details"))
        if isinstance(details, list) and details:
            extensions["reasoning_details"] = details

        return ApixAiMessage(
            content=_read(message, "content"),
            name=self.name,
            metadata=metadata,
            extensions=extensions,
            tool_calls=self._chat_tool_calls(_read(message, "tool_calls")),
            refusal=_read(message, "refusal"),
            reasoning=self._reasoning_from_message(message) or None,
            finish_reason=finish_reason,
        )

    @abstractmethod
    async def invoke(
        self,
        messages: list[AnyMessage],
        system_prompt: list[ApixSystemMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: Mapping[str, Any] | None = None,
    ) -> ApixAiMessage:
        """Invoke the provider and return one complete APIX AI message."""

    @abstractmethod
    async def stream(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[ApixAiMessageChunk]:
        """Stream provider deltas as APIX AI message chunks."""
        raise NotImplementedError


class BaseOpenAIBot(BaseBot):
    """Shared adapter for APIs implemented through the OpenAI Python SDK."""

    default_endpoint: str | None = None
    capabilities = ModelCapabilities(
        message_config=MessageConfig(
            supported_roles=("developer", "system", "user", "ai", "tool"),
        ),
        reasoning_config=ReasoningConfig(
            supported_efforts=("none", "low", "medium", "high"),
            effort_map={
                "low": "low",
                "medium": "medium",
                "high": "high",
            },
            disabled_effort="none",
        ),
    )

    def __init__(
        self,
        *,
        model: str,
        endpoint: str | None = None,
        api_key: str,
        capabilities: ModelCapabilities | None = None,
        role_schema: RoleSchema | None = None,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "api_key must be supplied explicitly; APIX does not read it "
                "from configuration or environment variables"
            )
        resolved_endpoint = endpoint or self.default_endpoint
        if resolved_endpoint is None:
            raise ValueError("endpoint must be supplied for this provider")
        super().__init__(
            model=model,
            endpoint=resolved_endpoint,
            api_key=api_key,
            capabilities=capabilities,
            role_schema=role_schema,
        )

        if client is None:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=self.endpoint,
                max_retries=LLM_MAX_RETRY,
                timeout=LLM_TIMEOUT,
            )
        self._client = client

    def _resolve_reasoning_effort(
        self,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
    ) -> str | None:
        config = self.capabilities.reasoning_config
        if reasoning:
            mapped = config.effort_map.get(
                reasoning_effort,
                reasoning_effort,
            )
        else:
            mapped = config.disabled_effort
        if mapped is None:
            return None

        supported = config.supported_efforts
        if supported and mapped not in supported:
            raise ValueError(
                f"{self.provider} does not support reasoning effort "
                f"{reasoning_effort!r} (mapped to {mapped!r})"
            )
        return mapped

    def _reasoning_request(
        self,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
    ) -> dict[str, Any]:
        config = self.capabilities.reasoning_config
        if not config.supported:
            return {}

        request = deepcopy(dict(config.request_defaults))
        effort = self._resolve_reasoning_effort(
            reasoning,
            reasoning_effort,
        )
        if effort is not None and config.effort_path:
            _set_path(request, config.effort_path, effort)
        return request

    def _provider_extra_body(
        self,
        extra_body: Mapping[str, Any] | None,
        *,
        reasoning: bool,
    ) -> dict[str, Any]:
        if extra_body is not None and not isinstance(extra_body, Mapping):
            raise TypeError("extra_body must be a mapping or None")

        request_config = self.capabilities.request_config
        reasoning_config = self.capabilities.reasoning_config
        reasoning_defaults = (
            reasoning_config.enabled_extra_body
            if reasoning
            else reasoning_config.disabled_extra_body
        )
        return _merge_mappings(
            request_config.extra_body_defaults,
            reasoning_config.extra_body_defaults,
            reasoning_defaults,
            extra_body or {},
        )

    def _chat_request(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
        *,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: Mapping[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        request_config = self.capabilities.request_config
        request = _merge_mappings(
            request_config.request_defaults,
            self._reasoning_request(reasoning, reasoning_effort),
            (
                self.capabilities.stream_config.request_defaults
                if stream
                else {}
            ),
        )
        request.update(
            {
                "model": self.model,
                "messages": self._prepare_api_messages(
                    messages,
                    system_prompt,
                ),
                "stream": stream,
            }
        )
        if self._tool_schemas and self.capabilities.tool_config.supported:
            request["tools"] = self.tool_schemas
        body = self._provider_extra_body(
            extra_body,
            reasoning=reasoning,
        )
        if body:
            request["extra_body"] = body
        return request

    @staticmethod
    def _responses_content(content: Any) -> Any:
        if not isinstance(content, list):
            return content

        converted: list[dict[str, Any]] = []
        for part in content:
            if not isinstance(part, Mapping):
                continue
            item = dict(part)
            part_type = item.get("type")
            if part_type == "text":
                converted.append(
                    {"type": "input_text", "text": item.get("text", "")}
                )
            elif part_type == "image_url":
                image_url = item.get("image_url")
                if isinstance(image_url, Mapping):
                    image_url = image_url.get("url")
                converted.append(
                    {"type": "input_image", "image_url": image_url}
                )
            else:
                converted.append(item)
        return converted

    def _convert_responses_message(
        self,
        message: ApixMessageBase,
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        if not isinstance(message, ApixMessageBase):
            raise TypeError(
                "message must be a complete ApixMessageBase instance"
            )
        if not self._supports_role(message.role):
            return None

        if isinstance(message, ApixToolMessage):
            return {
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": str(message.content or ""),
            }

        if isinstance(message, ApixAiMessage):
            retained = message.extensions.get("response_output")
            if isinstance(retained, list) and retained:
                return deepcopy(retained)

            items: list[dict[str, Any]] = []
            if message.content is not None:
                items.append(
                    {"role": "assistant", "content": message.content}
                )
            for tool_call in message.tool_calls:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": tool_call["call_id"],
                        "name": tool_call["tool_name"],
                        "arguments": json.dumps(
                            tool_call.get("args") or {},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                )
            return items or [{"role": "assistant", "content": ""}]

        return {
            "role": message.role,
            "content": self._responses_content(message.content),
        }

    def convert_message_for_api(
        self,
        message: ApixMessageBase,
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        if self.capabilities.request_config.api_style == "responses":
            return self._convert_responses_message(message)
        return super().convert_message_for_api(message)

    def _response_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for schema in self._tool_schemas:
            function = schema.get("function")
            if not isinstance(function, Mapping) or not function.get("name"):
                continue
            converted = {
                "type": "function",
                "name": function["name"],
                "description": function.get("description", ""),
                "parameters": deepcopy(function.get("parameters", {})),
            }
            if "strict" in function:
                converted["strict"] = bool(function["strict"])
            tools.append(converted)
        return tools

    def _responses_request(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
        *,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: Mapping[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        request_config = self.capabilities.request_config
        request = _merge_mappings(
            request_config.request_defaults,
            self._reasoning_request(reasoning, reasoning_effort),
            (
                self.capabilities.stream_config.request_defaults
                if stream
                else {}
            ),
        )
        request.update(
            {
                "model": self.model,
                "input": self._prepare_api_messages(
                    messages,
                    system_prompt,
                ),
                "stream": stream,
            }
        )
        if self._tool_schemas and self.capabilities.tool_config.supported:
            tools = self._response_tools()
            if tools:
                request["tools"] = tools
        body = self._provider_extra_body(
            extra_body,
            reasoning=reasoning,
        )
        if body:
            request["extra_body"] = body
        return request

    @staticmethod
    def _response_output(response: Any) -> list[Any]:
        value = _read(response, "output", [])
        return list(value) if value else []

    @staticmethod
    def _response_reasoning(output: list[Any]) -> str:
        parts: list[str] = []
        for item in output:
            if _read(item, "type") != "reasoning":
                continue
            for summary in _read(item, "summary", []) or []:
                text = _read(summary, "text")
                if text:
                    parts.append(str(text))
        return "".join(parts)

    @classmethod
    def _response_tool_calls(cls, output: list[Any]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in output:
            if _read(item, "type") != "function_call":
                continue
            call_id = _read(item, "call_id") or _read(item, "id")
            name = _read(item, "name")
            if not call_id or not name:
                raise ValueError(
                    "Responses function call is missing call_id/name"
                )
            calls.append(
                ToolCall(
                    call_id=str(call_id),
                    tool_name=str(name),
                    args=cls._parse_tool_arguments(
                        _read(item, "arguments")
                    ),
                )
            )
        return calls

    @staticmethod
    def _response_text(output: list[Any]) -> tuple[str | None, str | None]:
        text_parts: list[str] = []
        refusal_parts: list[str] = []
        for item in output:
            if _read(item, "type") != "message":
                continue
            for part in _read(item, "content", []) or []:
                part_type = _read(part, "type")
                if part_type == "output_text":
                    text_parts.append(str(_read(part, "text", "") or ""))
                elif part_type == "refusal":
                    refusal_parts.append(
                        str(_read(part, "refusal", "") or "")
                    )
        return (
            "".join(text_parts) or None,
            "".join(refusal_parts) or None,
        )

    @classmethod
    def _response_finish_reason(cls, response: Any) -> str:
        output = cls._response_output(response)
        if any(_read(item, "type") == "function_call" for item in output):
            return "tool_calls"

        status = _read(response, "status")
        if status == "incomplete":
            details = _read(response, "incomplete_details", {})
            reason = _read(details, "reason")
            return cls._normalize_finish_reason(reason) or "unknown"
        if status == "completed":
            return "stop"
        return "unknown"

    def _convert_responses_to_apix(
        self,
        response: Any,
        *,
        stream: bool,
        message_uid: str | None,
        duration: float | None,
    ) -> ApixAiMessage | ApixAiMessageChunk:
        if not stream:
            output = self._response_output(response)
            content, refusal = self._response_text(output)
            finish_reason = self._response_finish_reason(response)
            metadata = self._metadata(response, duration=duration)
            metadata["finish_reason"] = finish_reason
            return ApixAiMessage(
                content=content,
                name=self.name,
                metadata=metadata,
                extensions={"response_output": _model_dump(output)},
                tool_calls=self._response_tool_calls(output),
                refusal=refusal,
                reasoning=self._response_reasoning(output) or None,
                finish_reason=finish_reason,
            )

        event_type = str(_read(response, "type", "") or "")
        response_object = _read(response, "response")
        metadata = self._metadata(
            response_object or response,
            duration=duration,
        )
        response_id = _read(response, "response_id")
        if response_id:
            metadata["id"] = response_id

        content_delta = ""
        reasoning_delta = ""
        refusal_delta = ""
        tool_deltas: tuple[ToolCallDelta, ...] = ()
        finish_reason = None
        extensions: dict[str, Any] = {}

        if event_type == "response.output_text.delta":
            content_delta = str(_read(response, "delta", "") or "")
        elif event_type in {
            "response.reasoning_summary_text.delta",
            "response.reasoning_text.delta",
        }:
            reasoning_delta = str(_read(response, "delta", "") or "")
        elif event_type == "response.refusal.delta":
            refusal_delta = str(_read(response, "delta", "") or "")
        elif event_type == "response.output_item.added":
            item = _read(response, "item", {})
            if _read(item, "type") == "function_call":
                arguments = _read(item, "arguments", "")
                if isinstance(arguments, Mapping):
                    arguments = json.dumps(
                        dict(arguments),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                tool_deltas = (
                    ToolCallDelta(
                        index=int(_read(response, "output_index", 0)),
                        call_id_delta=str(
                            _read(item, "call_id", "") or ""
                        ),
                        tool_name_delta=str(_read(item, "name", "") or ""),
                        arguments_delta=str(arguments or ""),
                    ),
                )
        elif event_type == "response.function_call_arguments.delta":
            tool_deltas = (
                ToolCallDelta(
                    index=int(_read(response, "output_index", 0)),
                    arguments_delta=str(_read(response, "delta", "") or ""),
                ),
            )
        elif event_type in {
            "response.completed",
            "response.incomplete",
            "response.failed",
        }:
            completed = response_object or response
            finish_reason = self._response_finish_reason(completed)
            metadata = self._metadata(completed, duration=duration)
            metadata["finish_reason"] = finish_reason
            output = self._response_output(completed)
            if output:
                extensions["response_output"] = _model_dump(output)

        return ApixAiMessageChunk(
            content_delta=content_delta,
            reasoning_delta=reasoning_delta,
            refusal_delta=refusal_delta,
            tool_call_deltas=tool_deltas,
            finish_reason=finish_reason,
            message_uid=message_uid or uuid4().hex,
            name=self.name,
            metadata=metadata,
            extensions=extensions,
        )

    def convert_message_to_apix(
        self,
        response: Any,
        *,
        stream: bool = False,
        message_uid: str | None = None,
        duration: float | None = None,
    ) -> ApixAiMessage | ApixAiMessageChunk:
        if self.capabilities.request_config.api_style == "responses":
            return self._convert_responses_to_apix(
                response,
                stream=stream,
                message_uid=message_uid,
                duration=duration,
            )
        return super().convert_message_to_apix(
            response,
            stream=stream,
            message_uid=message_uid,
            duration=duration,
        )

    def _request(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
        *,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: Mapping[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        builder = (
            self._responses_request
            if self.capabilities.request_config.api_style == "responses"
            else self._chat_request
        )
        return builder(
            messages,
            system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            stream=stream,
        )

    async def invoke(
        self,
        messages: list[AnyMessage],
        system_prompt: list[ApixSystemMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: Mapping[str, Any] | None = None,
    ) -> ApixAiMessage:
        started = perf_counter()
        request = self._request(
            messages,
            system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            stream=False,
        )
        if self.capabilities.request_config.api_style == "responses":
            response = await self._client.responses.create(**request)
        else:
            response = await self._client.chat.completions.create(**request)

        converted = self.convert_message_to_apix(
            response,
            duration=perf_counter() - started,
        )
        if not isinstance(converted, ApixAiMessage):
            raise TypeError("provider returned a streaming chunk to invoke")
        return converted

    @staticmethod
    def _incremental_reasoning(
        current: str,
        previous: str,
    ) -> tuple[str, str]:
        if current.startswith(previous):
            return current[len(previous) :], current
        return current, previous + current

    async def stream(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[ApixAiMessageChunk]:
        started = perf_counter()
        request = self._request(
            messages,
            system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            stream=True,
        )
        if self.capabilities.request_config.api_style == "responses":
            response_stream = await self._client.responses.create(**request)
        else:
            response_stream = await self._client.chat.completions.create(
                **request
            )

        message_uid = uuid4().hex
        reasoning_snapshot = ""
        async for response in response_stream:
            converted = self.convert_message_to_apix(
                response,
                stream=True,
                message_uid=message_uid,
                duration=perf_counter() - started,
            )
            if not isinstance(converted, ApixAiMessageChunk):
                raise TypeError(
                    "provider returned a complete message to stream"
                )

            if (
                self.capabilities.reasoning_config.stream_delta_mode
                == "cumulative"
                and converted.reasoning_delta
            ):
                reasoning_delta, reasoning_snapshot = (
                    self._incremental_reasoning(
                        converted.reasoning_delta,
                        reasoning_snapshot,
                    )
                )
                converted = replace(
                    converted,
                    reasoning_delta=reasoning_delta,
                )

            if self.capabilities.request_config.api_style == "responses":
                if (
                    converted.has_delta
                    or converted.is_finished
                    or converted.extensions
                ):
                    yield converted
            else:
                yield converted
