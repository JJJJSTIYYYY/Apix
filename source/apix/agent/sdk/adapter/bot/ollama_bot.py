from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import replace
from time import perf_counter
from typing import Any
from uuid import uuid4

from apix.agent.sdk.adapter.bot.base import (
    MessageConfig,
    ModelCapabilities,
    ReasoningConfig,
    ReasoningEffort,
)
from apix.agent.sdk.adapter.bot.base_bot import (
    BaseBot,
    _model_dump,
    _read,
)
from apix.agent.sdk.utils.context import RoleSchema
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
from apix.config.base_config import LLM_TIMEOUT, PROVIDER_BASE_URL


class OllamaBot(BaseBot):
    """Adapter for Ollama's native ``/api/chat`` protocol."""

    provider = "ollama"
    capabilities = ModelCapabilities(
        message_config=MessageConfig(
            supported_roles=("system", "user", "ai", "tool"),
        ),
        reasoning_config=ReasoningConfig(
            effort_path=None,
            supported_efforts=("low", "medium", "high", "max"),
            effort_map={
                "low": "low",
                "medium": "medium",
                "high": "high",
            },
        ),
    )

    def __init__(
        self,
        *,
        model: str,
        endpoint: str | None = None,
        api_key: str = "",
        capabilities: ModelCapabilities | None = None,
        role_schema: RoleSchema | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(
            model=model,
            endpoint=(
                endpoint
                if endpoint is not None
                else PROVIDER_BASE_URL["ollama:local"]
            ),
            api_key=api_key,
            capabilities=capabilities,
            role_schema=role_schema,
        )
        if client is None:
            from ollama import AsyncClient

            headers = (
                {"Authorization": f"Bearer {api_key}"}
                if api_key
                else None
            )
            client = AsyncClient(
                host=self.endpoint,
                headers=headers,
                timeout=LLM_TIMEOUT,
            )
        self._client = client

    def convert_message_for_api(
        self,
        message: ApixMessageBase,
    ) -> dict[str, Any] | None:
        if not isinstance(message, ApixMessageBase):
            raise TypeError(
                "message must be a complete ApixMessageBase instance"
            )
        if not self._supports_role(message.role):
            return None

        if isinstance(message, ApixToolMessage):
            result = {
                "role": "tool",
                "content": str(message.content or ""),
            }
            if message.name:
                result["tool_name"] = message.name
            return result

        role = "assistant" if message.role == "ai" else message.role
        result: dict[str, Any] = {
            "role": role,
            "content": message.content or "",
        }
        if isinstance(message, ApixAiMessage):
            if message.reasoning:
                result["thinking"] = message.reasoning
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "function": {
                            "name": call["tool_name"],
                            "arguments": call.get("args") or {},
                        }
                    }
                    for call in message.tool_calls
                ]
        return result

    def _ollama_request(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
        *,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: Mapping[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        if extra_body is not None and not isinstance(extra_body, Mapping):
            raise TypeError("extra_body must be a mapping or None")
        request: dict[str, Any] = dict(extra_body or {})
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
        reasoning_config = self.capabilities.reasoning_config
        if reasoning_config.supported:
            effort = reasoning_config.effort_map.get(
                reasoning_effort,
                reasoning_effort,
            )
            supported = reasoning_config.supported_efforts
            if reasoning and supported and effort not in supported:
                raise ValueError(
                    f"ollama does not support reasoning effort "
                    f"{reasoning_effort!r} (mapped to {effort!r})"
                )
            request["think"] = effort if reasoning else False
        if self._tool_schemas and self.capabilities.tool_config.supported:
            request["tools"] = self.tool_schemas
        return request

    @classmethod
    def _ollama_tool_calls(cls, value: Any) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in value or []:
            function = _read(item, "function", {})
            name = _read(function, "name")
            if not name:
                raise ValueError("Ollama tool call has no function name")
            calls.append(
                ToolCall(
                    call_id=str(_read(item, "id") or f"call_{uuid4().hex}"),
                    tool_name=str(name),
                    args=cls._parse_tool_arguments(
                        _read(function, "arguments")
                    ),
                )
            )
        return calls

    @staticmethod
    def _ollama_tool_deltas(value: Any) -> tuple[ToolCallDelta, ...]:
        import json

        deltas: list[ToolCallDelta] = []
        for fallback_index, item in enumerate(value or []):
            function = _read(item, "function", {})
            arguments = _read(function, "arguments", {})
            if isinstance(arguments, Mapping):
                arguments = json.dumps(
                    dict(arguments),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            deltas.append(
                ToolCallDelta(
                    index=int(
                        _read(function, "index", fallback_index)
                    ),
                    call_id_delta=str(
                        _read(item, "id") or f"call_{uuid4().hex}"
                    ),
                    tool_name_delta=str(
                        _read(function, "name", "") or ""
                    ),
                    arguments_delta=str(arguments or ""),
                )
            )
        return tuple(deltas)

    def _ollama_metadata(
        self,
        response: Any,
        *,
        duration: float | None,
    ) -> dict[str, Any]:
        metadata = self._metadata(response, duration=duration)
        usage = {
            "prompt_tokens": _read(response, "prompt_eval_count"),
            "completion_tokens": _read(response, "eval_count"),
        }
        usage = {key: value for key, value in usage.items() if value is not None}
        if usage:
            usage["total_tokens"] = sum(usage.values())
            metadata["usage"] = usage
        total_duration = _read(response, "total_duration")
        if isinstance(total_duration, (int, float)):
            metadata["provider_duration"] = total_duration / 1_000_000_000
        return metadata

    def convert_message_to_apix(
        self,
        response: Any,
        *,
        stream: bool = False,
        message_uid: str | None = None,
        duration: float | None = None,
    ) -> ApixAiMessage | ApixAiMessageChunk:
        message = _read(response, "message", {})
        tool_calls_value = _read(message, "tool_calls")
        metadata = self._ollama_metadata(response, duration=duration)
        done = bool(_read(response, "done", False))
        finish_reason = None
        if done:
            finish_reason = (
                "tool_calls"
                if tool_calls_value
                else self._normalize_finish_reason(
                    _read(response, "done_reason", "stop")
                )
            )
            metadata["finish_reason"] = finish_reason

        if stream:
            return ApixAiMessageChunk(
                content_delta=str(_read(message, "content", "") or ""),
                reasoning_delta=str(_read(message, "thinking", "") or ""),
                tool_call_deltas=self._ollama_tool_deltas(tool_calls_value),
                finish_reason=finish_reason,
                message_uid=message_uid or uuid4().hex,
                name=self.name,
                metadata=metadata,
            )

        finish_reason = (
            "tool_calls"
            if tool_calls_value
            else self._normalize_finish_reason(
                _read(response, "done_reason", "stop")
            )
        )
        metadata["finish_reason"] = finish_reason
        return ApixAiMessage(
            content=_read(message, "content"),
            name=self.name,
            metadata=metadata,
            tool_calls=self._ollama_tool_calls(tool_calls_value),
            reasoning=_read(message, "thinking") or None,
            finish_reason=finish_reason,
            extensions={
                "ollama_message": _model_dump(message),
            },
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
        response = await self._client.chat(
            **self._ollama_request(
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
            raise TypeError("Ollama returned a chunk to invoke")
        return converted

    async def stream(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[ApixAiMessageChunk]:
        started = perf_counter()
        response_stream = await self._client.chat(
            **self._ollama_request(
                messages,
                system_prompt,
                reasoning=reasoning,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
                stream=True,
            )
        )
        message_uid = uuid4().hex
        saw_tool_calls = False
        async for response in response_stream:
            converted = self.convert_message_to_apix(
                response,
                stream=True,
                message_uid=message_uid,
                duration=perf_counter() - started,
            )
            if not isinstance(converted, ApixAiMessageChunk):
                raise TypeError("Ollama returned a message to stream")
            saw_tool_calls = saw_tool_calls or bool(
                converted.tool_call_deltas
            )
            if converted.is_finished and saw_tool_calls:
                metadata = dict(converted.metadata)
                metadata["finish_reason"] = "tool_calls"
                converted = replace(
                    converted,
                    finish_reason="tool_calls",
                    metadata=metadata,
                )
            yield converted
