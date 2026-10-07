from copy import deepcopy

from apix.agent.core.bot.base import ProviderResponseError
from apix.agent.core.bot.codec.base import (
    BaseCodec,
    StreamState,
    arguments,
    dump,
    finish_reason,
    function_schemas,
    json_arguments,
    read,
    text,
)
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixToolMessage,
    ToolCall,
    ToolCallDelta,
)


class ResponsesCodec(BaseCodec):
    @staticmethod
    def content_parts(content, *, assistant=False):
        if not isinstance(content, list):
            return content or ""
        result = []
        for part in deepcopy(content):
            kind = part.get("type")
            if kind == "text":
                part["type"] = "output_text" if assistant else "input_text"
            elif kind == "image_url":
                image = part["image_url"]
                part = {
                    "type": "input_image",
                    "image_url": image["url"] if isinstance(image, dict) else image,
                    **(
                        {"detail": image["detail"]}
                        if isinstance(image, dict) and "detail" in image
                        else {}
                    ),
                }
            result.append(part)
        return result

    def encode_message(self, message, *, has_tools=None):
        self.validate_message(message)
        if isinstance(message, ApixToolMessage):
            return {
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": message.content or "",
            }
        if isinstance(message, ApixAiMessage):
            replay = self.replay_reasoning(message, has_tools)
            if "response_output" in message.extensions:
                items = deepcopy(message.extensions["response_output"])
                for item in items:
                    if item.get("type") not in (
                        "message",
                        "reasoning",
                        "function_call",
                    ):
                        raise ValueError("provider-native output cannot be replayed")
                return [item for item in items if item["type"] != "reasoning" or replay]
            items = []
            if message.content:
                items.append(
                    {
                        "role": "assistant",
                        "content": self.content_parts(message.content, assistant=True),
                    }
                )
            if message.refusal:
                items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "refusal", "refusal": message.refusal}],
                    }
                )
            items.extend(
                {
                    "type": "function_call",
                    "call_id": call["call_id"],
                    "name": call["tool_name"],
                    "arguments": json_arguments(call.get("args")),
                }
                for call in message.tool_calls
            )
            return items or [{"role": "assistant", "content": ""}]
        return {"role": message.role, "content": self.content_parts(message.content)}

    def encode_request(self, messages, tools, tool_choice, parallel):
        result = {"input": self.encode_messages(messages, has_tools=bool(tools))}
        functions = function_schemas(tools)
        if functions:
            result["tools"] = [
                {"type": "function", **function} for function in functions
            ]
        if tool_choice is not None:
            result["tool_choice"] = (
                tool_choice
                if tool_choice in ("auto", "none", "required")
                else {"type": "function", "name": tool_choice}
            )
        if parallel is not None:
            result["parallel_tool_calls"] = parallel
        return result

    @staticmethod
    def response_finish(response, has_tools=False):
        if read(response, "status") == "failed" or read(response, "error"):
            raise ProviderResponseError(
                f"provider response failed: {dump(read(response, 'error'))}"
            )
        if read(response, "status") == "incomplete":
            return finish_reason(
                read(read(response, "incomplete_details", {}), "reason")
            )
        return (
            "tool_calls"
            if has_tools
            else finish_reason(read(response, "status")) or "stop"
        )

    @staticmethod
    def decode_tool_calls(items):
        calls = []
        for item in items or []:
            if not read(item, "call_id") or not read(item, "name"):
                raise ValueError("function call requires call_id and name")
            calls.append(
                ToolCall(
                    call_id=read(item, "call_id"),
                    tool_name=read(item, "name"),
                    args=arguments(read(item, "arguments")),
                )
            )
        return calls

    def decode_response(self, response, **context):
        values = self.values(response)
        if all(
            values[key] is None
            for key in ("content", "reasoning", "tool_calls", "refusal")
        ):
            raise ValueError("response contains no output")
        calls = self.decode_tool_calls(values["tool_calls"])
        extensions = values["extensions"]
        if read(response, "output") is not None:
            extensions.setdefault("response_output", dump(read(response, "output")))
        return ApixAiMessage(
            content=text(values["content"]) or None,
            reasoning=text(values["reasoning"]) or None,
            refusal=text(values["refusal"]) or None,
            tool_calls=calls,
            finish_reason=self.response_finish(response, bool(calls)),
            name=context.get("name", "assistant"),
            metadata=self.metadata(response, usage=values["usage"], **context),
            extensions=extensions,
        )

    def decode_stream(self, event, state: StreamState, **context):
        event_type = read(event, "type")
        if event_type in ("error", "response.failed"):
            raise ProviderResponseError(
                f"provider stream failed: {dump(read(event, 'error') or read(event, 'response'))}"
            )
        values = self.values(event, stream=True)
        tools = ()
        finish = None
        extensions = values["extensions"]
        response = read(event, "response") or event
        if (
            event_type == "response.reasoning_text.delta"
            and self.profile.reasoning.stream_output is None
        ):
            values["reasoning"] = read(event, "delta")
        if event_type == "response.output_item.added":
            item = read(event, "item", {})
            if read(item, "type") == "function_call":
                tools = (
                    ToolCallDelta(
                        index=int(read(event, "output_index", 0)),
                        call_id_delta=read(item, "call_id", "") or "",
                        tool_name_delta=read(item, "name", "") or "",
                        arguments_delta=json_arguments(
                            read(item, "arguments", "") or ""
                        ),
                    ),
                )
        elif event_type == "response.function_call_arguments.delta":
            tools = (
                ToolCallDelta(
                    index=int(read(event, "output_index", 0)),
                    arguments_delta=read(event, "delta", "") or "",
                ),
            )
        elif event_type == "response.output_item.done":
            state.data.setdefault("output", {})[int(read(event, "output_index", 0))] = (
                dump(read(event, "item", {}))
            )
        elif event_type in ("response.completed", "response.incomplete"):
            output = dump(read(response, "output"))
            if output is None:
                output = [
                    item for _, item in sorted(state.data.get("output", {}).items())
                ]
            extensions["response_output"] = output
            finish = self.response_finish(
                response,
                state.saw_tools
                or any(item.get("type") == "function_call" for item in output),
            )
            values["usage"] = read(response, "usage")
        metadata = self.metadata(response, usage=values["usage"], **context)
        if read(event, "response_id"):
            metadata["id"] = read(event, "response_id")
        return self.chunk(
            state,
            content=text(values["content"]),
            reasoning=text(values["reasoning"]),
            refusal=text(values["refusal"]),
            tools=tools,
            finish=finish,
            extensions=extensions,
            metadata=metadata,
            name=context.get("name", "assistant"),
        )
