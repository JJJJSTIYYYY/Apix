"""Provider-independent OpenAI-compatible chat model primitives."""

from __future__ import annotations

import copy
import json
import os
from collections.abc import AsyncIterator, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal, Self

from openai import AsyncOpenAI

from apix.agent.sdk.tool import Tool, ToolNode
from apix.agent.sdk.utils.message import (
    AnyMessage,
    ApixAiMessage,
    ApixAiMessageChunk,
    ApixDeveloperMessage,
    ApixSystemMessage,
    ApixToolMessage,
    ApixUserMessage,
    ToolCall,
    ToolCallDelta,
)
from apix.config.base_config import LLM_MAX_RETRY

ReasoningEffort = Literal["low", "medium", "high"]


def _get_field(value: Any, name: str, default: Any = None) -> Any:
    """Read one field from an SDK object or mapping."""
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _model_dump(value: Any) -> dict[str, Any]:
    """Convert SDK metadata to a plain dictionary when possible."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=True)
        return dumped if isinstance(dumped, dict) else {}

    return {}


def _iso_timestamp(created: Any, *, empty: bool = False) -> str:
    """Convert a provider Unix timestamp into the APIX timestamp format."""
    if isinstance(created, (int, float)):
        return datetime.fromtimestamp(
            created,
            tz=UTC,
        ).isoformat()
    if empty:
        return ""
    return datetime.now(UTC).isoformat()


def _finish_reason(value: Any) -> Literal[
    "stop",
    "length",
    "tool_calls",
    "content_filter",
    "unknown",
] | None:
    """Map provider stop reasons onto the APIX message vocabulary."""
    if value is None:
        return None
    if value in {
        "stop",
        "length",
        "tool_calls",
        "content_filter",
    }:
        return value
    return "unknown"


class OpenAICompatibleChatBot:
    """One configured chat bot backed by an OpenAI-compatible client."""

    supports_developer_role = False
    supports_reasoning_content = False
    reasoning_effort_map: Mapping[ReasoningEffort, str] | None = None
    disabled_reasoning_effort: str | None = None
    thinking_switch = False

    def __init__(
        self,
        *,
        client: Any,
        provider: str,
        model_name: str,
        name: str,
        role_definition: str | None = None,
    ) -> None:
        self.client = client
        self.provider = provider
        self.model_name = model_name
        self.name = name
        self.role_definition = role_definition
        self._tool_schemas: list[dict[str, Any]] = []

    def bind_tools(
        self,
        tool_set: Iterable[Tool] | ToolNode,
    ) -> Self:
        """Bind tool schemas to subsequent invoke and stream requests.

        Rebinding replaces the previous tool set. Passing an empty iterable
        clears the current binding.
        """
        if isinstance(tool_set, ToolNode):
            tool_node = tool_set
        elif isinstance(tool_set, Iterable):
            tools = list(tool_set)
            invalid_tool = next(
                (
                    candidate
                    for candidate in tools
                    if not isinstance(candidate, Tool)
                ),
                None,
            )
            if invalid_tool is not None:
                raise TypeError(
                    "tool_set must contain only Tool objects, "
                    f"got {type(invalid_tool).__name__}."
                )
            tool_node = ToolNode(tools)
        else:
            raise TypeError(
                "tool_set must be an iterable of Tool objects "
                "or a ToolNode."
            )

        self._tool_schemas = tool_node.get_schemas()
        return self

    def _convert_message(self, message: AnyMessage) -> dict[str, Any]:
        """Convert one complete APIX message to Chat Completions format."""
        if isinstance(message, ApixAiMessageChunk):
            raise TypeError(
                "ApixAiMessageChunk cannot be used as model input; "
                "aggregate it into ApixAiMessage first."
            )

        if isinstance(message, ApixSystemMessage):
            converted: dict[str, Any] = {
                "role": "system",
                "content": copy.deepcopy(message.content),
            }
        elif isinstance(message, ApixDeveloperMessage):
            converted = {
                "role": (
                    "developer"
                    if self.supports_developer_role
                    else "system"
                ),
                "content": copy.deepcopy(message.content),
            }
        elif isinstance(message, ApixUserMessage):
            converted = {
                "role": "user",
                "content": copy.deepcopy(message.content),
            }
        elif isinstance(message, ApixToolMessage):
            converted = {
                "role": "tool",
                "content": message.content,
                "tool_call_id": message.tool_call_id,
            }
        elif isinstance(message, ApixAiMessage):
            converted = {
                "role": "assistant",
                "content": copy.deepcopy(message.content),
            }

            if message.tool_calls:
                converted["tool_calls"] = [
                    {
                        "id": tool_call["call_id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["tool_name"],
                            "arguments": json.dumps(
                                tool_call["args"] or {},
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    }
                    for tool_call in message.tool_calls
                ]

            if (
                self.supports_reasoning_content
                and message.reasoning
            ):
                converted["reasoning_content"] = message.reasoning
        else:
            raise TypeError(
                "messages must contain APIX complete message objects, "
                f"got {type(message).__name__}."
            )

        if message.name:
            converted["name"] = message.name
        return converted

    def _build_messages(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage],
    ) -> list[dict[str, Any]]:
        """Insert the role definition between system and conversation input."""
        if not isinstance(messages, list):
            raise TypeError("messages must be a list.")
        if not isinstance(system_prompt, list):
            raise TypeError("system_prompt must be a list.")

        converted_system = [
            self._convert_message(message)
            for message in system_prompt
        ]
        converted_messages = [
            self._convert_message(message)
            for message in messages
        ]

        role_definition = (
            [
                {
                    "role": "system",
                    "content": self.role_definition,
                }
            ]
            if self.role_definition
            else []
        )

        return [
            *converted_system,
            *role_definition,
            *converted_messages,
        ]

    def _build_request(
        self,
        *,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage],
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: dict,
        stream: bool,
    ) -> dict[str, Any]:
        """Build one provider request without mutating caller-owned inputs."""
        if not isinstance(reasoning, bool):
            raise TypeError("reasoning must be a bool.")
        if reasoning_effort not in {"low", "medium", "high"}:
            raise ValueError(
                "reasoning_effort must be 'low', 'medium', or 'high'."
            )
        if not isinstance(extra_body, dict):
            raise TypeError("extra_body must be a dict.")

        request: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._build_messages(
                messages,
                system_prompt,
            ),
            "stream": stream,
        }
        request_extra_body = copy.deepcopy(extra_body)

        if self._tool_schemas:
            if "tools" in request_extra_body:
                raise ValueError(
                    "extra_body cannot define 'tools' when tools "
                    "are already bound to the chat bot."
                )
            request["tools"] = copy.deepcopy(self._tool_schemas)

        if reasoning and self.reasoning_effort_map is not None:
            request["reasoning_effort"] = self.reasoning_effort_map[
                reasoning_effort
            ]
        elif (
            not reasoning
            and self.disabled_reasoning_effort is not None
        ):
            request["reasoning_effort"] = (
                self.disabled_reasoning_effort
            )

        if self.thinking_switch:
            request_extra_body.setdefault(
                "thinking",
                {
                    "type": (
                        "enabled"
                        if reasoning
                        else "disabled"
                    )
                },
            )

        if request_extra_body:
            request["extra_body"] = request_extra_body
        return request

    @staticmethod
    def _parse_tool_calls(raw_tool_calls: Any) -> list[ToolCall]:
        """Convert complete provider tool calls into APIX tool calls."""
        tool_calls: list[ToolCall] = []

        for raw_tool_call in raw_tool_calls or []:
            function = _get_field(raw_tool_call, "function")
            call_id = _get_field(raw_tool_call, "id")
            tool_name = _get_field(function, "name")
            raw_arguments = _get_field(function, "arguments", "")

            if not isinstance(call_id, str) or not call_id:
                raise ValueError(
                    "Provider tool call is missing a call id."
                )
            if not isinstance(tool_name, str) or not tool_name:
                raise ValueError(
                    "Provider tool call is missing a function name."
                )

            arguments: dict[str, Any] | None = None
            if raw_arguments:
                try:
                    decoded_arguments = json.loads(raw_arguments)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"Provider tool {tool_name!r} returned invalid "
                        "JSON arguments."
                    ) from exc
                if not isinstance(decoded_arguments, dict):
                    raise ValueError(
                        f"Provider tool {tool_name!r} arguments must "
                        "decode to a JSON object."
                    )
                arguments = decoded_arguments

            tool_calls.append(
                ToolCall(
                    call_id=call_id,
                    tool_name=tool_name,
                    args=arguments,
                )
            )

        return tool_calls

    @staticmethod
    def _parse_tool_call_deltas(
        raw_tool_calls: Any,
    ) -> tuple[ToolCallDelta, ...]:
        """Convert streamed provider tool-call fragments."""
        deltas: list[ToolCallDelta] = []

        for raw_tool_call in raw_tool_calls or []:
            function = _get_field(raw_tool_call, "function")
            index = _get_field(raw_tool_call, "index", 0)
            if not isinstance(index, int) or index < 0:
                raise ValueError(
                    "Provider tool-call delta index must be >= 0."
                )

            deltas.append(
                ToolCallDelta(
                    index=index,
                    call_id_delta=(
                        _get_field(raw_tool_call, "id") or ""
                    ),
                    tool_name_delta=(
                        _get_field(function, "name") or ""
                    ),
                    arguments_delta=(
                        _get_field(function, "arguments") or ""
                    ),
                )
            )

        return tuple(deltas)

    def _response_info(
        self,
        response: Any,
        choice: Any = None,
    ) -> dict[str, Any]:
        """Build stable response metadata for complete messages and chunks."""
        info: dict[str, Any] = {
            "provider": self.provider,
            "model": (
                _get_field(response, "model")
                or self.model_name
            ),
        }
        usage = (
            _get_field(response, "usage")
            or _get_field(choice, "usage")
        )
        dumped_usage = _model_dump(usage)
        if dumped_usage:
            info["usage"] = dumped_usage
        return info

    def _to_message(self, response: Any) -> ApixAiMessage:
        """Convert one non-streaming Chat Completion response."""
        choices = _get_field(response, "choices", [])
        if not choices:
            raise RuntimeError(
                "Provider returned a chat completion without choices."
            )

        choice = next(
            (
                candidate
                for candidate in choices
                if _get_field(candidate, "index") == 0
            ),
            choices[0],
        )
        raw_message = _get_field(choice, "message")
        if raw_message is None:
            raise RuntimeError(
                "Provider chat completion choice has no message."
            )

        message_kwargs: dict[str, Any] = {
            "content": _get_field(raw_message, "content"),
            "name": self.name,
            "timestamp": _iso_timestamp(
                _get_field(response, "created")
            ),
            "info": self._response_info(response, choice),
            "tool_calls": self._parse_tool_calls(
                _get_field(raw_message, "tool_calls")
            ),
            "refusal": _get_field(raw_message, "refusal"),
            "reasoning": (
                _get_field(raw_message, "reasoning_content")
                or _get_field(raw_message, "reasoning")
            ),
            "finish_reason": _finish_reason(
                _get_field(choice, "finish_reason")
            ),
        }
        response_id = _get_field(response, "id")
        if isinstance(response_id, str) and response_id:
            message_kwargs["id"] = response_id

        return ApixAiMessage(**message_kwargs)

    def _to_chunk(self, response: Any) -> ApixAiMessageChunk:
        """Convert one streamed Chat Completion response chunk."""
        choices = _get_field(response, "choices", [])
        choice = next(
            (
                candidate
                for candidate in choices
                if _get_field(candidate, "index") == 0
            ),
            choices[0] if choices else None,
        )
        delta = _get_field(choice, "delta")

        return ApixAiMessageChunk(
            content_delta=(
                _get_field(delta, "content") or ""
            ),
            reasoning_delta=(
                _get_field(delta, "reasoning_content")
                or _get_field(delta, "reasoning")
                or ""
            ),
            refusal_delta=(
                _get_field(delta, "refusal") or ""
            ),
            tool_call_deltas=self._parse_tool_call_deltas(
                _get_field(delta, "tool_calls")
            ),
            finish_reason=_finish_reason(
                _get_field(choice, "finish_reason")
            ),
            id=_get_field(response, "id") or "",
            name=self.name,
            timestamp=_iso_timestamp(
                _get_field(response, "created"),
                empty=True,
            ),
            info=self._response_info(response, choice),
        )

    async def invoke(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] = [],  # noqa: B006
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict = {},  # noqa: B006
    ) -> ApixAiMessage:
        """Return one complete assistant message."""
        request = self._build_request(
            messages=messages,
            system_prompt=system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            stream=False,
        )
        response = await self.client.chat.completions.create(
            **request
        )
        return self._to_message(response)

    async def stream(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] = [],  # noqa: B006
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict = {},  # noqa: B006
    ) -> AsyncIterator[ApixAiMessageChunk]:
        """Yield assistant-message chunks from one streaming request."""
        request = self._build_request(
            messages=messages,
            system_prompt=system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            stream=True,
        )
        response_stream = await self.client.chat.completions.create(
            **request
        )

        async for response in response_stream:
            yield self._to_chunk(response)


class OpenAICompatibleProvider[
    ChatBotT: OpenAICompatibleChatBot
]:
    """Create configured chat bots for one OpenAI-compatible provider."""

    provider = ""
    api_key_env = ""
    default_base_url = ""
    chat_bot_class: type[ChatBotT]
    local_api_key: str | None = None

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        max_retries: int = LLM_MAX_RETRY,
        timeout: float | None = None,
        client: Any = None,
    ) -> None:
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer.")

        self.base_url = base_url or self.default_base_url
        self.api_key = (
            api_key
            or (
                os.getenv(self.api_key_env)
                if self.api_key_env
                else None
            )
            or self.local_api_key
        )
        self.max_retries = max_retries
        self.timeout = timeout

        if client is not None:
            self.client = client
            return

        if not self.api_key:
            raise ValueError(
                f"{self.provider} API key is required; pass api_key "
                f"or set {self.api_key_env}."
            )

        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "max_retries": self.max_retries,
        }
        if timeout is not None:
            client_kwargs["timeout"] = timeout

        self.client = AsyncOpenAI(**client_kwargs)

    def get_chat_bot(
        self,
        model_name: str,
        *,
        name: str | None = None,
        role_definition: str | None = None,
    ) -> ChatBotT:
        """Create a bot with a fixed model, name, and role definition."""
        if not isinstance(model_name, str) or not model_name:
            raise ValueError("model_name must be a non-empty string.")

        bot_name = model_name if name is None else name
        if not isinstance(bot_name, str) or not bot_name:
            raise ValueError("name must be a non-empty string.")
        if (
            role_definition is not None
            and not isinstance(role_definition, str)
        ):
            raise TypeError("role_definition must be a string or None.")

        return self.chat_bot_class(
            client=self.client,
            provider=self.provider,
            model_name=model_name,
            name=bot_name,
            role_definition=role_definition,
        )
