from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable, Mapping
from copy import deepcopy
import json
from time import perf_counter
from typing import Any, Self
from uuid import uuid4

from apix.agent.sdk.adapter.bot.base import (
    ModelCapabilities,
    ReasoningEffort,
)
from apix.agent.sdk.tool import Tool, ToolNode
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
        return {
            str(key): _model_dump(item)
            for key, item in value.items()
        }
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
        name: str,
        role_definition: str,
        endpoint: str,
        api_key: str,
        capabilities: ModelCapabilities | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(role_definition, str):
            raise TypeError("role_definition must be a string")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must be a non-empty string")
        if not isinstance(api_key, str):
            raise TypeError("api_key must be a string")

        self.model = model.strip()
        self.name = name.strip()
        self.role_definition = role_definition.strip()
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        if capabilities is not None:
            self.capabilities = capabilities
        self._tool_schemas: list[dict[str, Any]] = []

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        """Return an isolated copy of the currently bound tool schemas."""
        return deepcopy(self._tool_schemas)

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
        if self.role_definition:
            ordered.append(
                ApixSystemMessage(
                    content=self.role_definition,
                    name=self.name,
                )
            )
        ordered.extend(messages)
        return ordered

    def _supports_role(self, role: str) -> bool:
        supported = self.capabilities.supports_role
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
        """Serialize one APIX message to OpenAI Chat Completions format.

        Provider classes may override this method when their wire protocol is
        not Chat Completions compatible (OpenAI Responses and Ollama do so).
        Unsupported roles are intentionally filtered according to
        :class:`ModelCapabilities`.
        """
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

        result: dict[str, Any] = {
            "role": api_role,
            "content": content,
        }

        if self.capabilities.supports_name and message.name:
            result["name"] = message.name

        if isinstance(message, ApixAiMessage):
            if message.tool_calls:
                result["tool_calls"] = [
                    self._chat_tool_call(tool_call)
                    for tool_call in message.tool_calls
                ]
            if (
                self.capabilities.require_reasoning_content
                and message.reasoning is not None
            ):
                result["reasoning_content"] = message.reasoning
            if self.capabilities.require_reasoning_details:
                reasoning_details = message.extensions.get(
                    "reasoning_details"
                )
                if isinstance(reasoning_details, list):
                    result["reasoning_details"] = deepcopy(
                        reasoning_details
                    )

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
                str(_read(item, "text", "") or "")
                for item in details
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
        """Convert an OpenAI-compatible Chat response into APIX messages."""
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
        extra_body: dict[str, Any] = {},
    ) -> ApixAiMessage:
        """Invoke the provider and return one complete APIX AI message."""

    @abstractmethod
    async def stream(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict[str, Any] = {},
    ) -> AsyncIterator[ApixAiMessageChunk]:
        """Stream provider deltas as APIX AI message chunks."""
        if False:
            yield ApixAiMessageChunk()


class BaseOpenAIBot(BaseBot):
    """Base implementation for OpenAI Chat Completions compatible APIs."""

    capabilities = ModelCapabilities(
        supports_role=["developer", "system", "user", "ai", "tool"],
        supports_effort=["none", "low", "medium", "high"],
        reasoning_effort_map={
            "low": "low",
            "medium": "medium",
            "high": "high",
        },
    )

    def __init__(
        self,
        *,
        model: str,
        name: str = "assistant",
        role_definition: str = "",
        endpoint: str,
        api_key: str,
        capabilities: ModelCapabilities | None = None,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "api_key must be supplied explicitly; APIX does not read it "
                "from configuration or environment variables"
            )
        super().__init__(
            model=model,
            name=name,
            role_definition=role_definition,
            endpoint=endpoint,
            api_key=api_key,
            capabilities=capabilities,
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

    def _reasoning_request(
        self,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
    ) -> dict[str, Any]:
        if not self.capabilities.supports_reasoning:
            return {}

        if not reasoning:
            if "none" in self.capabilities.supports_effort:
                return {"reasoning_effort": "none"}
            return {}

        mapped = (
            self.capabilities.reasoning_effort_map or {}
        ).get(reasoning_effort, reasoning_effort)
        supported = self.capabilities.supports_effort
        if supported and mapped not in supported:
            raise ValueError(
                f"{self.provider} does not support reasoning effort "
                f"{reasoning_effort!r} (mapped to {mapped!r})"
            )
        return {"reasoning_effort": mapped}

    def _provider_extra_body(
        self,
        extra_body: dict[str, Any],
        *,
        reasoning: bool,
    ) -> dict[str, Any]:
        return dict(extra_body or {})

    def _chat_request(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
        *,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: dict[str, Any],
        stream: bool,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": self._prepare_api_messages(
                messages,
                system_prompt,
            ),
            "stream": stream,
        }
        if self._tool_schemas and self.capabilities.supports_tools:
            request["tools"] = self.tool_schemas

        request.update(
            self._reasoning_request(reasoning, reasoning_effort)
        )
        body = self._provider_extra_body(
            extra_body,
            reasoning=reasoning,
        )
        if body:
            request["extra_body"] = body
        if stream and self.capabilities.supports_stream_usage:
            request["stream_options"] = {"include_usage": True}
        return request

    async def invoke(
        self,
        messages: list[AnyMessage],
        system_prompt: list[ApixSystemMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict[str, Any] = {},
    ) -> ApixAiMessage:
        started = perf_counter()
        response = await self._client.chat.completions.create(
            **self._chat_request(
                messages,
                system_prompt,
                reasoning=reasoning,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
                stream=False,
            )
        )
        converted = self.convert_message_to_apix(
            response,
            duration=perf_counter() - started,
        )
        if not isinstance(converted, ApixAiMessage):
            raise TypeError("provider returned a streaming chunk to invoke")
        return converted

    async def stream(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict[str, Any] = {},
    ) -> AsyncIterator[ApixAiMessageChunk]:
        started = perf_counter()
        response_stream = await self._client.chat.completions.create(
            **self._chat_request(
                messages,
                system_prompt,
                reasoning=reasoning,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
                stream=True,
            )
        )
        message_uid = uuid4().hex
        async for response in response_stream:
            converted = self.convert_message_to_apix(
                response,
                stream=True,
                message_uid=message_uid,
                duration=perf_counter() - started,
            )
            if not isinstance(converted, ApixAiMessageChunk):
                raise TypeError("provider returned a complete message to stream")
            yield converted
