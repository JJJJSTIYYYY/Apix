from copy import deepcopy
from typing import Any

from apix.agent.core.bot.codec.base import (
    BaseCodec,
    StreamState,
    arguments,
    finish_reason,
    function_schemas,
    json_arguments,
    read,
    text,
)
from apix.agent.core.bot.profile import ResponseField
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixMessageBase,
    ApixToolMessage,
    ToolCall,
    ToolCallDelta,
)


class ChatCompletionsCodec(BaseCodec):
    def encode_message(self, message: ApixMessageBase, *, has_tools=None) -> dict:
        self.validate_message(message)
        result = {"role": message.role, "content": deepcopy(message.content) or ""}
        if self.profile.messages.supports_name and message.name:
            result["name"] = message.name
        if isinstance(message, ApixToolMessage):
            result["tool_call_id"] = message.tool_call_id
        if isinstance(message, ApixAiMessage):
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": call["call_id"],
                        "type": "function",
                        "function": {
                            "name": call["tool_name"],
                            "arguments": json_arguments(call.get("args")),
                        },
                    }
                    for call in message.tool_calls
                ]
            if self.replay_reasoning(message, has_tools):
                selector = (
                    self.profile.reasoning.output or self.schema.complete.reasoning
                )
                path = (
                    selector.path if isinstance(selector, ResponseField) else selector
                )
                projection = isinstance(selector, ResponseField) and (
                    selector.match is not None or selector.value
                )
                if (
                    message.reasoning is not None
                    and path
                    and not projection
                    and isinstance(path[-1], str)
                ):
                    result[path[-1]] = message.reasoning
                for key, selector in self.schema.complete.extensions.items():
                    path = (
                        selector.path
                        if isinstance(selector, ResponseField)
                        else selector
                    )
                    if (
                        key in message.extensions
                        and isinstance(path, tuple)
                        and path
                        and isinstance(path[-1], str)
                    ):
                        result[path[-1]] = deepcopy(message.extensions[key])
        return result

    def encode_request(self, messages, tools, tool_choice, parallel) -> dict:
        functions = function_schemas(tools)
        result = {"messages": self.encode_messages(messages, has_tools=bool(functions))}
        if functions:
            result["tools"] = [
                {"type": "function", "function": function} for function in functions
            ]
        if tool_choice is not None:
            result["tool_choice"] = (
                tool_choice
                if tool_choice in ("auto", "none", "required")
                else {"type": "function", "function": {"name": tool_choice}}
            )
        if parallel is not None:
            result["parallel_tool_calls"] = parallel
        return result

    @staticmethod
    def decode_tool_calls(items: Any) -> list[ToolCall]:
        result = []
        for item in items or []:
            function = read(item, "function", {})
            if not read(item, "id") or not read(function, "name"):
                raise ValueError("tool call requires an id and function name")
            result.append(
                ToolCall(
                    call_id=read(item, "id"),
                    tool_name=read(function, "name"),
                    args=arguments(read(function, "arguments")),
                )
            )
        return result

    @staticmethod
    def decode_tool_deltas(items: Any) -> tuple[ToolCallDelta, ...]:
        return tuple(
            ToolCallDelta(
                index=int(read(item, "index", index)),
                call_id_delta=read(item, "id", "") or "",
                tool_name_delta=read(read(item, "function", {}), "name", "") or "",
                arguments_delta=json_arguments(
                    read(read(item, "function", {}), "arguments", "") or ""
                ),
            )
            for index, item in enumerate(items or [])
        )

    def decode_response(self, response, **context) -> ApixAiMessage:
        values = self.values(response)
        if (
            all(
                values[key] is None
                for key in ("content", "reasoning", "tool_calls", "refusal")
            )
            and not values["extensions"]
        ):
            raise ValueError("response contains no choices or configured output fields")
        metadata = self.metadata(response, usage=values["usage"], **context)
        return ApixAiMessage(
            content=values["content"],
            reasoning=text(values["reasoning"]) or None,
            refusal=text(values["refusal"]) or None,
            tool_calls=self.decode_tool_calls(values["tool_calls"]),
            finish_reason=finish_reason(values["finish_reason"]),
            metadata=metadata,
            extensions=values["extensions"],
            name=context.get("name", "assistant"),
        )

    def decode_stream(self, event, state: StreamState, **context):
        values = self.values(event, stream=True)
        return self.chunk(
            state,
            content=text(values["content"]),
            reasoning=text(values["reasoning"]),
            refusal=text(values["refusal"]),
            tools=self.decode_tool_deltas(values["tool_calls"]),
            finish=finish_reason(values["finish_reason"]),
            extensions=values["extensions"],
            metadata=self.metadata(event, usage=values["usage"], **context),
            name=context.get("name", "assistant"),
        )
