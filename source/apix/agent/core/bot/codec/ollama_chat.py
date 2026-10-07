from uuid import uuid4

from apix.agent.core.bot.codec.base import (
    arguments,
    finish_reason,
    json_arguments,
    read,
)
from apix.agent.core.bot.codec.chat_completions import ChatCompletionsCodec
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixToolMessage,
    ToolCall,
    ToolCallDelta,
)


class OllamaChatCodec(ChatCompletionsCodec):
    def encode_message(self, message, *, has_tools=None):
        result = super().encode_message(message, has_tools=has_tools)
        if isinstance(message, ApixAiMessage):
            result.pop("reasoning_content", None)
            if message.reasoning and self.replay_reasoning(message, has_tools):
                result["thinking"] = message.reasoning
            for call in result.get("tool_calls", []):
                call["function"]["arguments"] = (
                    arguments(call["function"]["arguments"]) or {}
                )
        if isinstance(message, ApixToolMessage) and message.name:
            result["tool_name"] = message.name
        return result

    def encode_request(self, messages, tools, tool_choice, parallel):
        if tool_choice not in (None, "auto") or parallel is False:
            raise ValueError(
                "Ollama native chat does not support tool_choice or parallel_tool_calls"
            )
        return super().encode_request(messages, tools, None, None)

    def native_values(self, response):
        message = read(response, "message", {})
        usage = {
            "input_tokens": read(response, "prompt_eval_count", 0),
            "output_tokens": read(response, "eval_count", 0),
        }
        return message, usage

    def decode_response(self, response, **context):
        message, usage = self.native_values(response)
        calls = []
        for item in read(message, "tool_calls", []) or []:
            function = read(item, "function", {})
            if not read(function, "name"):
                raise ValueError("tool call requires a function name")
            calls.append(
                ToolCall(
                    call_id=read(item, "id") or f"call_{uuid4().hex}",
                    tool_name=read(function, "name"),
                    args=arguments(read(function, "arguments")),
                )
            )
        return ApixAiMessage(
            content=read(message, "content") or None,
            reasoning=read(message, "thinking") or None,
            tool_calls=calls,
            finish_reason="tool_calls"
            if calls
            else finish_reason(read(response, "done_reason", "stop")),
            metadata=self.metadata(response, usage=usage, **context),
            name=context.get("name", "assistant"),
        )

    def decode_stream(self, event, state, **context):
        message, usage = self.native_values(event)
        tools = []
        for item in read(message, "tool_calls", []) or []:
            function = read(item, "function", {})
            index = int(read(function, "index", state.data.get("tool_index", 0)))
            state.data["tool_index"] = index + 1
            tools.append(
                ToolCallDelta(
                    index=index,
                    call_id_delta=read(item, "id")
                    or f"call_{state.message_uid}_{index}",
                    tool_name_delta=read(function, "name", ""),
                    arguments_delta=json_arguments(read(function, "arguments")),
                )
            )
        return self.chunk(
            state,
            content=read(message, "content", "") or "",
            reasoning=read(message, "thinking", "") or "",
            tools=tuple(tools),
            finish=finish_reason(read(event, "done_reason", "stop"))
            if read(event, "done")
            else None,
            metadata=self.metadata(
                event, usage=usage if read(event, "done") else None, **context
            ),
            name=context.get("name", "assistant"),
        )
