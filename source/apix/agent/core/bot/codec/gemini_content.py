from copy import deepcopy
from uuid import uuid4

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


class GeminiContentCodec(BaseCodec):
    @staticmethod
    def content_parts(content):
        if not isinstance(content, list):
            return [{"text": content}] if content else []
        result = []
        for part in deepcopy(content):
            kind = part.get("type")
            if kind == "text":
                part = {"text": part["text"]}
            elif kind == "image_url":
                image = part["image_url"]
                url = image["url"] if isinstance(image, dict) else image
                if url.startswith("data:"):
                    header, data = url.split(",", 1)
                    part = {
                        "inlineData": {
                            "mimeType": header[5:].split(";")[0],
                            "data": data,
                        }
                    }
                else:
                    raise ValueError(
                        "Gemini images require inlineData or a native fileData part"
                    )
            result.append(part)
        return result

    def encode_message(self, message, *, has_tools=None):
        self.validate_message(message)
        if isinstance(message, ApixToolMessage):
            if not message.name:
                raise ValueError(
                    "Gemini tool results require a name or matching tool call in history"
                )
            return {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": message.name,
                            "response": {"result": message.content or ""},
                        }
                    }
                ],
            }
        parts = self.content_parts(message.content)
        if isinstance(message, ApixAiMessage):
            if "gemini_parts" in message.extensions:
                parts = deepcopy(message.extensions["gemini_parts"])
                if any(
                    set(part) - {"text", "thought", "thoughtSignature", "functionCall"}
                    for part in parts
                ):
                    raise ValueError("provider-native parts cannot be replayed")
                if not self.replay_reasoning(message, has_tools):
                    parts = [part for part in parts if not part.get("thought")]
            else:
                parts.extend(
                    {
                        "functionCall": {
                            "id": call["call_id"],
                            "name": call["tool_name"],
                            "args": deepcopy(call.get("args") or {}),
                        }
                    }
                    for call in message.tool_calls
                )
        return {
            "role": "model" if message.role == "assistant" else message.role,
            "parts": parts,
        }

    def encode_request(self, messages, tools, tool_choice, parallel):
        system = []
        encoded = []
        call_names = {}
        provider_ids = set()
        for message in messages:
            self.validate_message(message)
            if isinstance(message, ApixAiMessage):
                call_names.update(
                    {call["call_id"]: call["tool_name"] for call in message.tool_calls}
                )
                for part in message.extensions.get("gemini_parts", []):
                    if part.get("functionCall", {}).get("id"):
                        provider_ids.add(part["functionCall"]["id"])
            if message.role in ("system", "developer"):
                system.extend(self.content_parts(message.content))
                continue
            if isinstance(message, ApixToolMessage) and not message.name:
                message = ApixToolMessage(
                    tool_call_id=message.tool_call_id,
                    content=message.content,
                    name=call_names.get(message.tool_call_id),
                )
            item = self.encode_message(message, has_tools=bool(tools))
            if (
                isinstance(message, ApixToolMessage)
                and message.tool_call_id in provider_ids
            ):
                item["parts"][0]["functionResponse"]["id"] = message.tool_call_id
            if encoded and encoded[-1]["role"] == item["role"]:
                encoded[-1]["parts"].extend(item["parts"])
            else:
                encoded.append(item)
        result = {"contents": encoded}
        if system:
            result["systemInstruction"] = {"parts": system}
        functions = function_schemas(tools)
        if functions:
            result["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            key: value
                            for key, value in function.items()
                            if key in ("name", "description", "parameters")
                        }
                        for function in functions
                    ]
                }
            ]
        if tool_choice is not None:
            config = {
                "mode": {"auto": "AUTO", "none": "NONE", "required": "ANY"}.get(
                    tool_choice, "ANY"
                )
            }
            if tool_choice not in ("auto", "none", "required"):
                config["allowedFunctionNames"] = [tool_choice]
            result["toolConfig"] = {"functionCallingConfig": config}
        if parallel is False:
            raise ValueError(
                "Gemini does not expose a disable-parallel function calling option"
            )
        return result

    def decode_tool_calls(self, parts, *, uid=None):
        calls = []
        for index, part in enumerate(parts or []):
            call = read(part, "functionCall")
            if call is None:
                continue
            if not read(call, "name"):
                raise ValueError("function call requires a name")
            calls.append(
                ToolCall(
                    call_id=read(call, "id") or f"call_{uid or uuid4().hex}_{index}",
                    tool_name=read(call, "name"),
                    args=arguments(read(call, "args")),
                )
            )
        return calls

    def decode_response(self, response, **context):
        values = self.values(response)
        if read(response, "error"):
            raise ProviderResponseError(
                f"provider response failed: {dump(read(response, 'error'))}"
            )
        if not read(response, "candidates") and all(
            values[key] is None for key in ("content", "reasoning", "tool_calls")
        ):
            raise ProviderResponseError(
                f"provider returned no candidates: {dump(read(response, 'promptFeedback'))}"
            )
        calls = self.decode_tool_calls(values["tool_calls"])
        return ApixAiMessage(
            content=text(values["content"]) or None,
            reasoning=text(values["reasoning"]) or None,
            tool_calls=calls,
            finish_reason="tool_calls"
            if calls
            else finish_reason(values["finish_reason"]),
            metadata=self.metadata(response, usage=values["usage"], **context),
            name=context.get("name", "assistant"),
            extensions={
                **values["extensions"],
                "gemini_parts": dump(values["tool_calls"]) or [],
            },
        )

    def decode_stream(self, event, state: StreamState, **context):
        # GenerateContent uses the same candidate structure for each stream item.
        if read(event, "error"):
            raise ProviderResponseError(
                f"provider stream failed: {dump(read(event, 'error'))}"
            )
        if read(event, "promptFeedback") and not read(event, "candidates"):
            raise ProviderResponseError("provider blocked the prompt")
        values = self.values(event, stream=True)
        parts = dump(values["tool_calls"]) or []
        retained = state.data.setdefault("parts", [])
        tools = []
        for part in parts:
            if (
                "text" in part
                or "thoughtSignature" in part
                and "functionCall" not in part
            ):
                if (
                    retained
                    and "text" in retained[-1]
                    and not retained[-1].get("thoughtSignature")
                    and bool(retained[-1].get("thought")) == bool(part.get("thought"))
                ):
                    retained[-1]["text"] += part.get("text", "")
                    if "thoughtSignature" in part:
                        retained[-1]["thoughtSignature"] = part["thoughtSignature"]
                else:
                    retained.append(deepcopy(part))
            else:
                retained.append(deepcopy(part))
            if "functionCall" in part:
                call = self.decode_tool_calls([part], uid=state.message_uid)[0]
                index = state.data.get("tool_index", 0)
                state.data["tool_index"] = index + 1
                if not part["functionCall"].get("id"):
                    call["call_id"] = f"call_{state.message_uid}_{index}"
                tools.append(
                    ToolCallDelta(
                        index=index,
                        call_id_delta=call["call_id"],
                        tool_name_delta=call["tool_name"],
                        arguments_delta=json_arguments(call["args"]),
                    )
                )
        finish = finish_reason(values["finish_reason"])
        extensions = {**values["extensions"], "gemini_parts": deepcopy(retained)}
        return self.chunk(
            state,
            content=text(values["content"]),
            reasoning=text(values["reasoning"]),
            tools=tuple(tools),
            finish=finish,
            extensions=extensions,
            metadata=self.metadata(event, usage=values["usage"], **context),
            name=context.get("name", "assistant"),
        )
