"""Public primitives for OpenAI-compatible chat model adapters.

The public classes live here for backwards compatibility. Request
serialization and response parsing are delegated to focused modules.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterable, Mapping
from time import perf_counter
from typing import Any, Self

from openai import AsyncOpenAI

from apix.agent.sdk.adapter.model import _utils
from apix.agent.sdk.adapter.model.request import ChatRequestBuilder
from apix.agent.sdk.adapter.model.response import (
    ChatResponseParser,
    StreamResponseState,
)
from apix.agent.sdk.adapter.model.base import (
    ModelCapabilities,
    ReasoningEffort,
)
from apix.agent.sdk.tool import Tool, ToolNode
from apix.agent.sdk.utils.message import (
    AnyMessage,
    ApixAiMessage,
    ApixAiMessageChunk,
    ToolCall,
    ToolCallDelta,
    _new_message_id,
)
from apix.config.base_config import LLM_MAX_RETRY, LLM_TIMEOUT

elapsed_milliseconds = _utils.elapsed_milliseconds
token_usage_info = _utils.token_usage_info
_finish_reason = _utils.normalize_finish_reason
_get_field = _utils.get_field
_iso_timestamp = _utils.iso_timestamp
_model_dump = _utils.model_dump

__all__ = [
    "OpenAICompatibleChatBot",
    "OpenAICompatibleProvider",
    "ReasoningEffort",
    "_finish_reason",
    "_get_field",
    "_iso_timestamp",
    "_model_dump",
    "token_usage_info",
]


class OpenAICompatibleChatBot:
    """A configured chat bot backed by an OpenAI-compatible client."""

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

        capabilities = ModelCapabilities(
            supports_developer_role=self.supports_developer_role,
            supports_reasoning_content=self.supports_reasoning_content,
            reasoning_effort_map=self.reasoning_effort_map,
            disabled_reasoning_effort=self.disabled_reasoning_effort,
            thinking_switch=self.thinking_switch,
        )
        self._request_builder = ChatRequestBuilder(
            model_name=model_name,
            role_definition=role_definition,
            capabilities=capabilities,
        )
        self._response_parser = ChatResponseParser(
            provider=provider,
            model_name=model_name,
            name=name,
        )

    def bind_tools(
        self,
        tool_set: Iterable[Tool] | ToolNode,
    ) -> Self:
        """Replace the schemas bound to subsequent model requests."""
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

    # Compatibility delegates for callers that used the earlier private API.
    def _convert_message(self, message: AnyMessage) -> dict[str, Any]:
        return self._request_builder.convert_message(message)

    def _build_messages(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage],
    ) -> list[dict[str, Any]]:
        return self._request_builder.build_messages(
            messages,
            system_prompt,
        )

    def _build_request(
        self,
        *,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage],
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: dict[str, Any],
        stream: bool,
    ) -> dict[str, Any]:
        return self._request_builder.build(
            messages=messages,
            system_prompt=system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            stream=stream,
            tool_schemas=self._tool_schemas,
        )

    @staticmethod
    def _parse_tool_calls(raw_tool_calls: Any) -> list[ToolCall]:
        return ChatResponseParser.parse_tool_calls(raw_tool_calls)

    @staticmethod
    def _parse_tool_call_deltas(
        raw_tool_calls: Any,
    ) -> tuple[ToolCallDelta, ...]:
        return ChatResponseParser.parse_tool_call_deltas(raw_tool_calls)

    def _response_info(
        self,
        response: Any,
        choice: Any = None,
        *,
        total_duration: int = 0,
    ) -> dict[str, Any]:
        response_id = _get_field(response, "id") or _new_message_id()
        return self._response_parser.response_info(
            response,
            choice,
            message_id=response_id,
            total_duration=total_duration,
        )

    def _to_message(
        self,
        response: Any,
        *,
        total_duration: int = 0,
    ) -> ApixAiMessage:
        return self._response_parser.to_message(
            response,
            total_duration=total_duration,
        )

    def _to_chunk(
        self,
        response: Any,
        *,
        message_id: str | None = None,
        total_duration: int = 0,
    ) -> ApixAiMessageChunk:
        return self._response_parser.to_chunk(
            response,
            message_id=message_id or _get_field(response, "id") or "",
            total_duration=total_duration,
        )

    async def invoke(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict[str, Any] | None = None,
    ) -> ApixAiMessage:
        """Return one complete assistant message."""
        request = self._build_request(
            messages=messages,
            system_prompt=[] if system_prompt is None else system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body={} if extra_body is None else extra_body,
            stream=False,
        )
        started_at = perf_counter()
        response = await self.client.chat.completions.create(**request)
        return self._to_message(
            response,
            total_duration=elapsed_milliseconds(started_at),
        )

    async def stream(
        self,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage] | None = None,
        reasoning: bool = True,
        reasoning_effort: ReasoningEffort = "high",
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncIterator[ApixAiMessageChunk]:
        """Yield normalized assistant-message chunks."""
        request = self._build_request(
            messages=messages,
            system_prompt=[] if system_prompt is None else system_prompt,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body={} if extra_body is None else extra_body,
            stream=True,
        )
        started_at = perf_counter()
        response_stream = await self.client.chat.completions.create(**request)
        state = StreamResponseState()

        async for response in response_stream:
            chunk = self._to_chunk(
                response,
                message_id=state.resolve_message_id(response),
                total_duration=elapsed_milliseconds(started_at),
            )
            yield state.add(chunk)


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
        timeout: float = LLM_TIMEOUT,
        client: Any = None,
    ) -> None:
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer.")

        self.base_url = base_url or self.default_base_url
        self.api_key = (
            api_key
            or (os.getenv(self.api_key_env) if self.api_key_env else None)
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
