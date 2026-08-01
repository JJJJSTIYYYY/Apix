from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from copy import deepcopy
import json
from time import perf_counter
from typing import Any
from uuid import uuid4

from apix.agent.sdk.adapter.bot.base import (
    ModelCapabilities,
    ReasoningEffort,
)
from apix.agent.sdk.adapter.bot.base_bot import (
    BaseOpenAIBot,
    _model_dump,
    _read,
)
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
from apix.config.base_config import PROVIDER_BASE_URL


class OpenAIBot(BaseOpenAIBot):
    """OpenAI adapter using the Responses API.

    Responses output items are retained in ``extensions['response_output']``
    so stateless tool loops can send reasoning/function items back without
    flattening away provider state.
    """

    provider = "openai"
    capabilities = ModelCapabilities(
        supports_role=["developer", "system", "user", "ai", "tool"],
        supports_effort=[
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ],
        reasoning_effort_map={
            "low": "low",
            "medium": "medium",
            "high": "high",
        },
        api_style="responses",
    )

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        name: str = "assistant",
        role_definition: str = "",
        endpoint: str | None = None,
        capabilities: ModelCapabilities | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(
            model=model,
            name=name,
            role_definition=role_definition,
            endpoint=(
                endpoint
                if endpoint is not None
                else PROVIDER_BASE_URL["openai"]
            ),
            api_key=api_key,
            capabilities=capabilities,
            client=client,
        )

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

    def convert_message_for_api(
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
                    {
                        "role": "assistant",
                        "content": message.content,
                    }
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

    def _response_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for schema in self._tool_schemas:
            function = schema.get("function")
            if not isinstance(function, Mapping):
                continue
            tools.append(
                {
                    "type": "function",
                    "name": function.get("name"),
                    "description": function.get("description", ""),
                    "parameters": deepcopy(
                        function.get("parameters", {})
                    ),
                }
            )
        return tools

    def _responses_request(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None,
        *,
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: dict[str, Any],
        stream: bool,
    ) -> dict[str, Any]:
        effort = (
            (self.capabilities.reasoning_effort_map or {}).get(
                reasoning_effort,
                reasoning_effort,
            )
            if reasoning
            else "none"
        )
        request: dict[str, Any] = {
            "model": self.model,
            "input": self._prepare_api_messages(messages, system_prompt),
            "store": False,
            "stream": stream,
        }
        if self.capabilities.supports_reasoning:
            request["reasoning"] = {"effort": effort}
            request["include"] = ["reasoning.encrypted_content"]
        tools = self._response_tools()
        if tools:
            request["tools"] = tools
        if extra_body:
            request["extra_body"] = dict(extra_body)
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
                raise ValueError("OpenAI function call is missing call_id/name")
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

    def convert_message_to_apix(
        self,
        response: Any,
        *,
        stream: bool = False,
        message_uid: str | None = None,
        duration: float | None = None,
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
                extensions={
                    "response_output": _model_dump(output),
                },
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
                        tool_name_delta=str(
                            _read(item, "name", "") or ""
                        ),
                        arguments_delta=str(arguments or ""),
                    ),
                )
        elif event_type == "response.function_call_arguments.delta":
            tool_deltas = (
                ToolCallDelta(
                    index=int(_read(response, "output_index", 0)),
                    arguments_delta=str(
                        _read(response, "delta", "") or ""
                    ),
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

    async def invoke(
        self,
        messages: list[AnyMessage],
        system_prompt: list[ApixSystemMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict[str, Any] = {},
    ) -> ApixAiMessage:
        started = perf_counter()
        response = await self._client.responses.create(
            **self._responses_request(
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
            raise TypeError("Responses API returned a chunk to invoke")
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
        response_stream = await self._client.responses.create(
            **self._responses_request(
                messages,
                system_prompt,
                reasoning=reasoning,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
                stream=True,
            )
        )
        message_uid = uuid4().hex
        async for event in response_stream:
            converted = self.convert_message_to_apix(
                event,
                stream=True,
                message_uid=message_uid,
                duration=perf_counter() - started,
            )
            if not isinstance(converted, ApixAiMessageChunk):
                raise TypeError("Responses API returned a message to stream")
            if (
                converted.has_delta
                or converted.is_finished
                or converted.extensions
            ):
                yield converted
