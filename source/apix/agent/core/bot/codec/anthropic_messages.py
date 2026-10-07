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


class AnthropicMessagesCodec(BaseCodec):
    @staticmethod
    def content_parts(content):
        if not isinstance(content, list):
            return [{"type": "text", "text": content}] if content else []
        result = []
        for part in deepcopy(content):
            if part.get("type") == "image_url":
                image = part["image_url"]
                url = image["url"] if isinstance(image, dict) else image
                if url.startswith("data:"):
                    header, data = url.split(",", 1)
                    part = {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": header[5:].split(";")[0],
                            "data": data,
                        },
                    }
                else:
                    part = {"type": "image", "source": {"type": "url", "url": url}}
            result.append(part)
        return result

    def encode_message(self, message, *, has_tools=None):
        self.validate_message(message)
        if isinstance(message, ApixToolMessage):
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id,
                        "content": message.content or "",
                    }
                ],
            }
        content = self.content_parts(message.content)
        if isinstance(message, ApixAiMessage):
            if "anthropic_content" in message.extensions:
                content = deepcopy(message.extensions["anthropic_content"])
                if any(
                    part.get("type")
                    not in ("text", "thinking", "redacted_thinking", "tool_use")
                    for part in content
                ):
                    raise ValueError("provider-native content cannot be replayed")
                if not self.replay_reasoning(message, has_tools):
                    content = [
                        part
                        for part in content
                        if part["type"] not in ("thinking", "redacted_thinking")
                    ]
            else:
                if message.reasoning and self.replay_reasoning(message, has_tools):
                    raise ValueError(
                        "Anthropic reasoning replay requires original signed content blocks"
                    )
                content.extend(
                    {
                        "type": "tool_use",
                        "id": call["call_id"],
                        "name": call["tool_name"],
                        "input": deepcopy(call.get("args") or {}),
                    }
                    for call in message.tool_calls
                )
        return {"role": message.role, "content": content}

    def encode_request(self, messages, tools, tool_choice, parallel):
        system = []
        encoded = []
        for message in messages:
            self.validate_message(message)
            if message.role in ("system", "developer"):
                system.extend(self.content_parts(message.content))
                continue
            item = self.encode_message(message, has_tools=bool(tools))
            if encoded and encoded[-1]["role"] == item["role"]:
                encoded[-1]["content"].extend(item["content"])
            else:
                encoded.append(item)
        result = {"messages": encoded}
        if system:
            result["system"] = system
        functions = function_schemas(tools)
        if functions:
            result["tools"] = [
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                }
                for fn in functions
            ]
        if tool_choice is not None:
            result["tool_choice"] = (
                {"type": {"required": "any"}.get(tool_choice, tool_choice)}
                if tool_choice in ("auto", "none", "required")
                else {"type": "tool", "name": tool_choice}
            )
        if parallel is not None and functions and tool_choice != "none":
            result.setdefault("tool_choice", {"type": "auto"})[
                "disable_parallel_tool_use"
            ] = not parallel
        return result

    def decode_response(self, response, **context):
        if read(response, "type") == "error":
            raise ProviderResponseError(
                f"provider response failed: {dump(read(response, 'error'))}"
            )
        values = self.values(response)
        if all(values[key] is None for key in ("content", "reasoning", "tool_calls")):
            raise ValueError("response contains no content blocks")
        extensions = values["extensions"]
        if read(response, "content") is not None:
            extensions.setdefault("anthropic_content", dump(read(response, "content")))
        calls = []
        for item in values["tool_calls"] or []:
            if not read(item, "id") or not read(item, "name"):
                raise ValueError("tool use requires an id and name")
            calls.append(
                ToolCall(
                    call_id=read(item, "id"),
                    tool_name=read(item, "name"),
                    args=arguments(read(item, "input")),
                )
            )
        return ApixAiMessage(
            content=text(values["content"]) or None,
            reasoning=text(values["reasoning"]) or None,
            tool_calls=calls,
            finish_reason=finish_reason(values["finish_reason"]),
            name=context.get("name", "assistant"),
            metadata=self.metadata(response, usage=values["usage"], **context),
            extensions=extensions,
        )

    def decode_stream(self, event, state: StreamState, **context):
        kind = read(event, "type")
        if kind == "error":
            raise ProviderResponseError(
                f"provider stream failed: {dump(read(event, 'error'))}"
            )
        values = self.values(event, stream=True)
        tools = ()
        index = int(read(event, "index", 0))
        blocks = state.data.setdefault("blocks", {})
        usage = state.data.setdefault("usage", {})
        response = state.data.setdefault("message", {})
        extensions = values["extensions"]
        if kind == "message_start":
            response.update(dump(read(event, "message", {})))
            usage.update(response.get("usage", {}))
        elif kind == "content_block_start":
            block = dump(read(event, "content_block", {}))
            blocks[index] = block
            if block.get("type") == "tool_use":
                initial = json_arguments(block["input"]) if block.get("input") else ""
                tools = (
                    ToolCallDelta(
                        index=index,
                        call_id_delta=block.get("id", ""),
                        tool_name_delta=block.get("name", ""),
                        arguments_delta=initial,
                    ),
                )
                state.data.setdefault("arguments", {})[index] = initial
            elif block.get("type") == "text":
                values["content"] = block.get("text", "")
            elif block.get("type") == "thinking":
                values["reasoning"] = block.get("thinking", "")
        elif kind == "content_block_delta":
            delta = dump(read(event, "delta", {}))
            block = blocks.get(index)
            if block is None:
                raise ProviderResponseError("content delta has no matching block start")
            delta_kind = delta.get("type")
            field = {
                "text_delta": "text",
                "thinking_delta": "thinking",
                "signature_delta": "signature",
            }.get(delta_kind)
            if field:
                block[field] = block.get(field, "") + delta.get(field, "")
            elif delta_kind == "input_json_delta":
                fragment = delta.get("partial_json", "")
                state.data["arguments"][index] += fragment
                tools = (ToolCallDelta(index=index, arguments_delta=fragment),)
        elif kind == "content_block_stop":
            block = blocks.get(index, {})
            if block.get("type") == "tool_use":
                raw = state.data["arguments"].get(index, "")
                if raw:
                    block["input"] = arguments(raw)
                else:
                    tools = (
                        ToolCallDelta(
                            index=index,
                            arguments_delta=json_arguments(block.get("input")),
                        ),
                    )
        elif kind == "message_delta":
            usage.update(dump(values["usage"]) or {})
            state.data["finish"] = finish_reason(values["finish_reason"])
        elif kind == "message_stop":
            extensions["anthropic_content"] = [
                deepcopy(block) for _, block in sorted(blocks.items())
            ]
        finish = state.data.get("finish", "stop") if kind == "message_stop" else None
        return self.chunk(
            state,
            content=text(values["content"]),
            reasoning=text(values["reasoning"]),
            tools=tools,
            finish=finish,
            extensions=extensions,
            metadata=self.metadata(response, usage=usage, **context),
            name=context.get("name", "assistant"),
        )
