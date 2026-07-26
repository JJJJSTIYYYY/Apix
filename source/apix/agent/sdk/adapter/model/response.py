"""Parsing of OpenAI-compatible Chat Completions responses."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any

from apix.agent.sdk.adapter.model._utils import (
    get_field,
    iso_timestamp,
    normalize_finish_reason,
    token_usage_info,
)
from apix.agent.sdk.utils.message import (
    ApixAiMessage,
    ApixAiMessageChunk,
    ToolCall,
    ToolCallDelta,
    _new_message_id,
    tuple_delta_to_tool_calls,
)
from apix.common.type import ChunkMergeError


def tool_calls_extra(tool_calls: list[ToolCall]) -> dict[str, Any]:
    """Return the persistence-friendly representation of AI tool calls."""
    if not tool_calls:
        return {}
    return {
        "tool_calls": [
            {
                "id": tool_call["call_id"],
                "args": deepcopy(tool_call["args"] or {}),
                "name": tool_call["tool_name"],
                "type": "tool_call",
            }
            for tool_call in tool_calls
        ]
    }


@dataclass(frozen=True, slots=True)
class ChatResponseParser:
    """Normalize complete and streamed provider responses."""

    provider: str
    model_name: str
    name: str

    @staticmethod
    def select_choice(response: Any) -> Any:
        """Select choice zero, falling back to the first provider choice."""
        choices = get_field(response, "choices", [])
        return next(
            (
                candidate
                for candidate in choices
                if get_field(candidate, "index") == 0
            ),
            choices[0] if choices else None,
        )

    @staticmethod
    def parse_tool_calls(raw_tool_calls: Any) -> list[ToolCall]:
        """Convert complete provider tool calls into APIX tool calls."""
        tool_calls: list[ToolCall] = []
        for raw_tool_call in raw_tool_calls or []:
            function = get_field(raw_tool_call, "function")
            call_id = get_field(raw_tool_call, "id")
            tool_name = get_field(function, "name")
            raw_arguments = get_field(function, "arguments", "")

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
    def parse_tool_call_deltas(
        raw_tool_calls: Any,
    ) -> tuple[ToolCallDelta, ...]:
        """Convert streamed provider tool-call fragments."""
        deltas: list[ToolCallDelta] = []
        for raw_tool_call in raw_tool_calls or []:
            function = get_field(raw_tool_call, "function")
            index = get_field(raw_tool_call, "index", 0)
            if not isinstance(index, int) or index < 0:
                raise ValueError(
                    "Provider tool-call delta index must be >= 0."
                )
            deltas.append(
                ToolCallDelta(
                    index=index,
                    call_id_delta=get_field(raw_tool_call, "id") or "",
                    tool_name_delta=get_field(function, "name") or "",
                    arguments_delta=(
                        get_field(function, "arguments") or ""
                    ),
                )
            )
        return tuple(deltas)

    def response_info(
        self,
        response: Any,
        choice: Any,
        *,
        message_id: str,
        total_duration: int,
    ) -> dict[str, Any]:
        """Build the flat metadata contract consumed by context storage."""
        info: dict[str, Any] = {
            "id": message_id,
            "name": self.name,
            "model": get_field(response, "model") or self.model_name,
            "model_provider": self.provider,
            "total_duration": total_duration,
        }
        usage = get_field(response, "usage") or get_field(choice, "usage")
        info.update(token_usage_info(usage))
        return info

    def to_message(
        self,
        response: Any,
        *,
        total_duration: int = 0,
    ) -> ApixAiMessage:
        """Convert one non-streaming Chat Completion response."""
        choices = get_field(response, "choices", [])
        if not choices:
            raise RuntimeError(
                "Provider returned a chat completion without choices."
            )

        choice = self.select_choice(response)
        raw_message = get_field(choice, "message")
        if raw_message is None:
            raise RuntimeError(
                "Provider chat completion choice has no message."
            )

        response_id = get_field(response, "id")
        message_id = (
            response_id
            if isinstance(response_id, str) and response_id
            else _new_message_id()
        )
        tool_calls = self.parse_tool_calls(
            get_field(raw_message, "tool_calls")
        )
        return ApixAiMessage(
            id=message_id,
            content=get_field(raw_message, "content"),
            name=self.name,
            timestamp=iso_timestamp(get_field(response, "created")),
            info=self.response_info(
                response,
                choice,
                message_id=message_id,
                total_duration=total_duration,
            ),
            extra=tool_calls_extra(tool_calls),
            tool_calls=tool_calls,
            refusal=get_field(raw_message, "refusal"),
            reasoning=(
                get_field(raw_message, "reasoning_content")
                or get_field(raw_message, "reasoning")
            ),
            finish_reason=normalize_finish_reason(
                get_field(choice, "finish_reason")
            ),
        )

    def to_chunk(
        self,
        response: Any,
        *,
        message_id: str,
        total_duration: int = 0,
    ) -> ApixAiMessageChunk:
        """Convert one streamed Chat Completion response chunk."""
        choice = self.select_choice(response)
        delta = get_field(choice, "delta")
        return ApixAiMessageChunk(
            content_delta=get_field(delta, "content") or "",
            reasoning_delta=(
                get_field(delta, "reasoning_content")
                or get_field(delta, "reasoning")
                or ""
            ),
            refusal_delta=get_field(delta, "refusal") or "",
            tool_call_deltas=self.parse_tool_call_deltas(
                get_field(delta, "tool_calls")
            ),
            finish_reason=normalize_finish_reason(
                get_field(choice, "finish_reason")
            ),
            id=message_id,
            name=self.name,
            timestamp=iso_timestamp(
                get_field(response, "created"),
                empty=True,
            ),
            info=self.response_info(
                response,
                choice,
                message_id=message_id,
                total_duration=total_duration,
            ),
        )


@dataclass(slots=True)
class StreamResponseState:
    """Track identity and complete tool calls across streamed chunks."""

    message_id: str = ""
    aggregate: ApixAiMessageChunk = field(
        default_factory=ApixAiMessageChunk
    )

    def resolve_message_id(self, response: Any) -> str:
        """Return one stable ID even when a provider omits it on a chunk."""
        provider_id = get_field(response, "id")
        if not self.message_id:
            self.message_id = (
                provider_id
                if isinstance(provider_id, str) and provider_id
                else _new_message_id()
            )
        elif (
            isinstance(provider_id, str)
            and provider_id
            and provider_id != self.message_id
        ):
            raise ChunkMergeError(
                "provider changed the response id during one stream: "
                f"{self.message_id!r} != {provider_id!r}"
            )
        return self.message_id

    def add(self, chunk: ApixAiMessageChunk) -> ApixAiMessageChunk:
        """Accumulate a chunk and attach completed tool calls at finish."""
        aggregate = self.aggregate + chunk
        if chunk.finish_reason is not None and aggregate.tool_call_deltas:
            extra = tool_calls_extra(
                tuple_delta_to_tool_calls(aggregate.tool_call_deltas)
            )
            chunk = replace(chunk, extra=extra)
            aggregate = replace(
                aggregate,
                extra={**aggregate.extra, **extra},
            )
        self.aggregate = aggregate
        return chunk
