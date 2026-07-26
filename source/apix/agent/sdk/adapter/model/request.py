"""Serialization of APIX messages into Chat Completions requests."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from apix.agent.sdk.adapter.model.base import (
    ModelCapabilities,
    ReasoningEffort,
)
from apix.agent.sdk.utils.message import (
    AnyMessage,
    ApixAiMessage,
    ApixAiMessageChunk,
    ApixDeveloperMessage,
    ApixSystemMessage,
    ApixToolMessage,
    ApixUserMessage,
)


@dataclass(frozen=True, slots=True)
class ChatRequestBuilder:
    """Build provider requests without mutating caller-owned values."""

    model_name: str
    role_definition: str | None
    capabilities: ModelCapabilities

    def convert_message(self, message: AnyMessage) -> dict[str, Any]:
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
                    if self.capabilities.supports_developer_role
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
                self.capabilities.supports_reasoning_content
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

    def build_messages(
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
            self.convert_message(message)
            for message in system_prompt
        ]
        converted_messages = [
            self.convert_message(message)
            for message in messages
        ]
        role_definition = (
            [{"role": "system", "content": self.role_definition}]
            if self.role_definition
            else []
        )
        return [
            *converted_system,
            *role_definition,
            *converted_messages,
        ]

    def build(
        self,
        *,
        messages: list[AnyMessage],
        system_prompt: list[AnyMessage],
        reasoning: bool,
        reasoning_effort: ReasoningEffort,
        extra_body: dict[str, Any],
        stream: bool,
        tool_schemas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build one validated Chat Completions request."""
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
            "messages": self.build_messages(messages, system_prompt),
            "stream": stream,
        }
        if stream:
            request["stream_options"] = {"include_usage": True}
        request_extra_body = copy.deepcopy(extra_body)

        if tool_schemas:
            if "tools" in request_extra_body:
                raise ValueError(
                    "extra_body cannot define 'tools' when tools "
                    "are already bound to the chat bot."
                )
            request["tools"] = copy.deepcopy(tool_schemas)

        effort_map = self.capabilities.reasoning_effort_map
        if reasoning and effort_map is not None:
            request["reasoning_effort"] = effort_map[reasoning_effort]
        elif (
            not reasoning
            and self.capabilities.disabled_reasoning_effort is not None
        ):
            request["reasoning_effort"] = (
                self.capabilities.disabled_reasoning_effort
            )

        if self.capabilities.thinking_switch:
            request_extra_body.setdefault(
                "thinking",
                {"type": "enabled" if reasoning else "disabled"},
            )

        if request_extra_body:
            request["extra_body"] = request_extra_body
        return request
