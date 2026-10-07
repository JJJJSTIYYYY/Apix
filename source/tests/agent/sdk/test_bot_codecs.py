import pytest

from apix.agent.core.bot import (
    Bot,
    CustomProfile,
    ModelProfile,
    ProviderResponseError,
    ReasoningProfile,
    ResponseField,
    ResponseLayout,
    ResponseSchema,
    StreamField,
)
from apix.agent.core.bot.codec.base import arguments
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixAiMessageAccumulator,
    ApixDeveloperMessage,
    ApixToolMessage,
    ApixUserMessage,
)
from tests.agent.sdk.test_bot import RecordingProtocol, completion, make_bot, weather


def accumulate(chunks):
    accumulator = ApixAiMessageAccumulator()
    for chunk in chunks:
        accumulator.add(chunk)
    return accumulator.to_message(require_finished=True)


@pytest.mark.parametrize(
    "replay,with_tools,expected",
    [
        ("never", False, False),
        ("never", True, False),
        ("always", False, True),
        ("always", True, True),
        ("when_tools", False, False),
        ("when_tools", True, True),
    ],
)
def test_chat_reasoning_replay_does_not_depend_on_field_guessing(
    replay, with_tools, expected
):
    profile = ModelProfile(reasoning=ReasoningProfile(mode="always", replay=replay))
    bot = make_bot(model_profile=profile)
    message = ApixAiMessage(
        content="answer",
        reasoning="think",
        tool_calls=[{"call_id": "c1", "tool_name": "weather", "args": {}}]
        if with_tools
        else [],
    )
    serialized = bot.convert_message_for_api(message)
    assert ("reasoning_content" in serialized) is expected
    response = completion()
    response["choices"][0]["message"]["thinking"] = "must not guess"
    assert bot.convert_message_to_apix(response).reasoning is None


def test_schema_override_parses_complete_stream_usage_and_nested_extension():
    schema = ResponseSchema(
        complete=ResponseLayout(
            content=("result", 0, "answer"),
            reasoning=("result", 0, "thought"),
            finish_reason=("meta", "finish"),
            usage=("meta", "usage"),
            extensions={"opaque": ("meta", "opaque")},
        ),
        stream=ResponseLayout(
            content=StreamField(("kind",), "token", ("value",)),
            reasoning=StreamField(("kind",), "thinking", ("value",)),
        ),
    )
    bot = make_bot(custom_profile=CustomProfile(response_schema=schema))
    response = bot.convert_message_to_apix(
        {
            "result": [{"answer": "hi", "thought": "why"}],
            "meta": {
                "finish": "stop",
                "usage": {"input_tokens": 4, "output_tokens": 2},
                "opaque": {"data": 1},
            },
        }
    )
    assert response.content == "hi"
    assert response.reasoning == "why"
    assert response.metadata["usage"]["total_tokens"] == 6
    assert response.extensions["opaque"] == {"data": 1}
    assert (
        bot.convert_message_to_apix(
            {"kind": "token", "value": "hi"}, stream=True
        ).content_delta
        == "hi"
    )


def test_explicit_reasoning_output_override_takes_precedence_over_schema():
    reason = ReasoningProfile(
        mode="always",
        output=ResponseField(("special", "thought")),
        stream_output=StreamField(("type",), "thinking", ("text",)),
    )
    bot = make_bot(custom_profile=CustomProfile(reasoning=reason))
    raw = completion(reasoning="default")
    raw["special"] = {"thought": "override"}
    assert bot.convert_message_to_apix(raw).reasoning == "override"
    assert (
        bot.convert_message_to_apix(
            {"type": "thinking", "text": "override"}, stream=True
        ).reasoning_delta
        == "override"
    )


def test_replay_uses_the_declared_reasoning_field_and_usage_counts_hidden_tokens():
    reason = ReasoningProfile(
        mode="always",
        output=ResponseField(("choices", 0, "message", "thinking")),
        replay="always",
    )
    bot = make_bot(custom_profile=CustomProfile(reasoning=reason))
    serialized = bot.convert_message_for_api(ApixAiMessage(reasoning="why"))
    assert serialized["thinking"] == "why"
    assert "reasoning_content" not in serialized
    assert (
        bot._codec.decode_usage(
            {
                "input_tokens": 2,
                "output_tokens": 3,
                "cache_creation_input_tokens": 4,
                "cache_read_input_tokens": 5,
            }
        )["total_tokens"]
        == 14
    )
    assert (
        bot._codec.decode_usage(
            {"promptTokenCount": 2, "candidatesTokenCount": 3, "thoughtsTokenCount": 5}
        )["total_tokens"]
        == 10
    )


def test_chat_multimodal_inputs_names_roles_and_tool_argument_errors():
    parts = [
        {"type": "text", "text": "what?"},
        {"type": "image_url", "image_url": {"url": "https://example.test/a.png"}},
    ]
    bot = make_bot()
    serialized = bot.convert_message_for_api(
        ApixUserMessage(content=parts, name="user")
    )
    assert serialized["name"] == "user"
    serialized["content"][0]["text"] = "changed"
    assert parts[0]["text"] == "what?"
    with pytest.raises(ValueError, match="role"):
        bot.build_request([ApixDeveloperMessage(content="must not silently drop")])
    with pytest.raises(ValueError, match="JSON"):
        arguments("{")
    with pytest.raises(TypeError, match="object"):
        arguments("[]")
    with pytest.raises(TypeError):
        arguments(1)
    with pytest.raises(ValueError, match="function name"):
        bot.convert_message_to_apix(completion(calls=[{"id": "c1", "function": {}}]))
    with pytest.raises(ValueError, match="no choices"):
        bot.convert_message_to_apix({"choices": []})


def responses_output():
    return [
        {
            "type": "reasoning",
            "id": "r1",
            "summary": [{"type": "summary_text", "text": "thinking"}],
            "encrypted_content": "opaque",
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "checking"}],
        },
        {
            "type": "function_call",
            "id": "fc1",
            "call_id": "c1",
            "name": "weather",
            "arguments": '{"city":"Tokyo"}',
        },
    ]


@pytest.mark.asyncio
async def test_responses_replays_encrypted_reasoning_without_server_state():
    output = responses_output()
    transport = RecordingProtocol(
        {
            "id": "response-1",
            "status": "completed",
            "output": output,
            "usage": {"input_tokens": 3, "output_tokens": 5},
        }
    )
    bot = Bot(provider="openai", model="gpt-5.2", protocol=transport)
    response = await bot.invoke(
        [ApixUserMessage(content="weather?")], tools=[weather], reasoning_effort="high"
    )
    assert response.content == "checking"
    assert response.reasoning == "thinking"
    assert response.finish_reason == "tool_calls"
    request = bot.build_request(
        [response, ApixToolMessage(tool_call_id="c1", content="sunny")]
    )
    assert request["input"][:3] == output
    assert request["input"][-1] == {
        "type": "function_call_output",
        "call_id": "c1",
        "output": "sunny",
    }
    assert request["store"] is False
    assert request["include"] == ["reasoning.encrypted_content"]
    assert "previous_response_id" not in request
    assert transport.calls[0]["tools"][0]["type"] == "function"
    disabled = Bot(
        provider="openai",
        model="gpt-5.2",
        protocol=RecordingProtocol(),
        custom_profile=CustomProfile(reasoning=ReasoningProfile(replay="never")),
    )
    assert len(disabled.convert_message_for_api(response)) == 2


@pytest.mark.asyncio
async def test_responses_stream_preserves_final_output_without_duplicate_deltas():
    output = responses_output()
    events = [
        {"type": "response.created", "response": {"id": "response-1"}},
        {"type": "response.reasoning_summary_text.delta", "delta": "thinking"},
        {"type": "response.output_text.delta", "delta": "checking"},
        {
            "type": "response.output_item.added",
            "output_index": 2,
            "item": {**output[2], "arguments": ""},
        },
        {
            "type": "response.function_call_arguments.delta",
            "output_index": 2,
            "delta": '{"city":',
        },
        {
            "type": "response.function_call_arguments.delta",
            "output_index": 2,
            "delta": '"Tokyo"}',
        },
        {
            "type": "response.function_call_arguments.done",
            "output_index": 2,
            "arguments": '{"city":"Tokyo"}',
        },
        {
            "type": "response.completed",
            "response": {
                "status": "completed",
                "output": output,
                "usage": {"total_tokens": 8},
            },
        },
    ]
    bot = Bot(
        provider="openai", model="gpt-5.2", protocol=RecordingProtocol(events=events)
    )
    response = accumulate([chunk async for chunk in bot.stream([])])
    assert response.content == "checking"
    assert response.reasoning == "thinking"
    assert response.tool_calls[0]["args"] == {"city": "Tokyo"}
    assert response.extensions["response_output"] == output
    assert response.finish_reason == "tool_calls"


@pytest.mark.parametrize(
    "event",
    [
        {"type": "error", "error": {"message": "failed"}},
        {
            "type": "response.failed",
            "response": {"status": "failed", "error": {"message": "failed"}},
        },
    ],
)
def test_response_stream_errors_are_not_successful_finishes(event):
    bot = Bot(provider="openai", model="gpt-5.2", protocol=RecordingProtocol())
    with pytest.raises(ProviderResponseError):
        bot.convert_message_to_apix(event, stream=True)


def test_responses_refusal_incomplete_and_multimodal_encoding():
    bot = Bot(provider="openai", model="gpt-5.2", protocol=RecordingProtocol())
    response = bot.convert_message_to_apix(
        {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "refusal", "refusal": "cannot"}],
                }
            ],
        }
    )
    assert response.refusal == "cannot"
    assert response.finish_reason == "length"
    encoded = bot.convert_message_for_api(
        ApixUserMessage(
            content=[
                {"type": "text", "text": "hi"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://test/a.png", "detail": "low"},
                },
            ]
        )
    )
    assert encoded["content"] == [
        {"type": "input_text", "text": "hi"},
        {"type": "input_image", "image_url": "https://test/a.png", "detail": "low"},
    ]
    with pytest.raises(ValueError, match="native"):
        bot.convert_message_for_api(
            ApixAiMessage(extensions={"response_output": [{"type": "web_search_call"}]})
        )


def anthropic_content():
    return [
        {"type": "thinking", "thinking": "why", "signature": "signed"},
        {"type": "text", "text": "checking"},
        {"type": "tool_use", "id": "c1", "name": "weather", "input": {"city": "Tokyo"}},
    ]


def test_anthropic_complete_signed_blocks_tools_system_and_parallel_results():
    bot = Bot(
        provider="anthropic", model="claude-sonnet-4-6", protocol=RecordingProtocol()
    )
    response = bot.convert_message_to_apix(
        {
            "content": anthropic_content(),
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 3, "output_tokens": 5},
        }
    )
    assert response.content == "checking"
    assert response.reasoning == "why"
    assert response.finish_reason == "tool_calls"
    from apix.agent.core.utils.message import ApixSystemMessage

    request = bot.build_request(
        [
            ApixSystemMessage(content="global"),
            response,
            ApixToolMessage(tool_call_id="c1", content="sunny"),
            ApixToolMessage(tool_call_id="c2", content="rainy"),
        ],
        tools=[weather],
        tool_choice="auto",
        parallel_tool_calls=False,
    )
    assert request["system"] == [{"type": "text", "text": "global"}]
    assert request["messages"][0]["content"] == anthropic_content()
    assert len(request["messages"][1]["content"]) == 2
    assert request["tools"][0]["input_schema"]["type"] == "object"
    assert request["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}


@pytest.mark.asyncio
async def test_anthropic_stream_reassembles_json_signatures_and_cumulative_usage():
    events = [
        {
            "type": "message_start",
            "message": {"id": "m1", "usage": {"input_tokens": 3, "output_tokens": 1}},
        },
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "thinking", "thinking": "", "signature": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "thinking_delta", "thinking": "why"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "signature_delta", "signature": "signed"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {"type": "text", "text": ""},
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "text_delta", "text": "checking"},
        },
        {"type": "content_block_stop", "index": 1},
        {
            "type": "content_block_start",
            "index": 2,
            "content_block": {
                "type": "tool_use",
                "id": "c1",
                "name": "weather",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 2,
            "delta": {"type": "input_json_delta", "partial_json": '{"city":'},
        },
        {
            "type": "content_block_delta",
            "index": 2,
            "delta": {"type": "input_json_delta", "partial_json": '"Tokyo"}'},
        },
        {"type": "content_block_stop", "index": 2},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"output_tokens": 5},
        },
        {"type": "message_stop"},
    ]
    bot = Bot(
        provider="anthropic",
        model="claude-sonnet-4-6",
        protocol=RecordingProtocol(events=events),
    )
    response = accumulate([chunk async for chunk in bot.stream([])])
    assert response.reasoning == "why"
    assert response.tool_calls[0]["args"] == {"city": "Tokyo"}
    assert response.metadata["usage"] == {
        "input_tokens": 3,
        "output_tokens": 5,
        "total_tokens": 8,
    }
    assert response.extensions["anthropic_content"] == anthropic_content()
    assert bot.convert_message_for_api(response)["content"] == anthropic_content()


@pytest.mark.parametrize("initial", [{}, {"city": "Tokyo"}])
@pytest.mark.asyncio
async def test_anthropic_stream_handles_complete_or_empty_initial_tool_input(initial):
    events = [
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "type": "tool_use",
                "id": "c1",
                "name": "weather",
                "input": initial,
            },
        },
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
        {"type": "message_stop"},
    ]
    bot = Bot(
        provider="anthropic",
        model="claude-sonnet-4-6",
        protocol=RecordingProtocol(events=events),
    )
    response = accumulate([chunk async for chunk in bot.stream([])])
    assert response.tool_calls[0]["args"] == initial


def gemini_response(parts, finish="STOP", usage=None):
    return {
        "candidates": [
            {"content": {"role": "model", "parts": parts}, "finishReason": finish}
        ],
        "usageMetadata": usage,
    }


def test_gemini_parts_thought_signatures_and_named_results_round_trip():
    bot = Bot(
        provider="gemini", model="gemini-3-pro-preview", protocol=RecordingProtocol()
    )
    parts = [
        {"text": "why", "thought": True},
        {"text": "checking"},
        {
            "functionCall": {"id": "c1", "name": "weather", "args": {"city": "Tokyo"}},
            "thoughtSignature": "signed",
        },
    ]
    response = bot.convert_message_to_apix(
        gemini_response(parts, usage={"promptTokenCount": 2, "candidatesTokenCount": 4})
    )
    assert response.content == "checking"
    assert response.reasoning == "why"
    assert response.tool_calls[0]["call_id"] == "c1"
    request = bot.build_request(
        [response, ApixToolMessage(tool_call_id="c1", content="sunny")],
        tools=[weather],
        tool_choice="weather",
    )
    assert request["contents"][0]["parts"] == parts
    assert request["contents"][1]["parts"][0]["functionResponse"] == {
        "id": "c1",
        "name": "weather",
        "response": {"result": "sunny"},
    }
    assert request["toolConfig"]["functionCallingConfig"] == {
        "mode": "ANY",
        "allowedFunctionNames": ["weather"],
    }
    assert request["tools"][0]["functionDeclarations"][0]["name"] == "weather"
    assert response.metadata["usage"]["total_tokens"] == 6


@pytest.mark.asyncio
async def test_gemini_stream_merges_signed_text_and_preserves_parallel_calls():
    events = [
        gemini_response([{"thought": True, "text": "why "}], None),
        gemini_response(
            [{"thought": True, "text": "now", "thoughtSignature": "sig1"}], None
        ),
        gemini_response([{"text": "checking"}], None),
        gemini_response(
            [
                {
                    "functionCall": {"name": "weather", "args": {"city": "Tokyo"}},
                    "thoughtSignature": "sig2",
                },
                {"functionCall": {"name": "weather", "args": {"city": "Paris"}}},
            ],
            "STOP",
            {"totalTokenCount": 9},
        ),
    ]
    bot = Bot(
        provider="gemini",
        model="gemini-3-pro-preview",
        protocol=RecordingProtocol(events=events),
    )
    response = accumulate([chunk async for chunk in bot.stream([])])
    assert response.reasoning == "why now"
    assert response.content == "checking"
    assert len({call["call_id"] for call in response.tool_calls}) == 2
    assert response.finish_reason == "tool_calls"
    assert response.extensions["gemini_parts"][0] == {
        "thought": True,
        "text": "why now",
        "thoughtSignature": "sig1",
    }
    request = bot.build_request(
        [
            response,
            ApixToolMessage(
                tool_call_id=response.tool_calls[0]["call_id"], content="sunny"
            ),
        ]
    )
    assert request["contents"][1]["parts"][0]["functionResponse"]["name"] == "weather"


@pytest.mark.asyncio
async def test_ollama_native_chat_handles_tool_calls_and_usage_without_sdk():
    raw = {
        "message": {
            "content": "checking",
            "thinking": "why",
            "tool_calls": [
                {"function": {"name": "weather", "arguments": {"city": "Tokyo"}}}
            ],
        },
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 2,
        "eval_count": 3,
    }
    bot = Bot(
        provider="ollama", model="qwen3", protocol=RecordingProtocol(raw, events=[raw])
    )
    response = await bot.invoke([], tools=[weather], reasoning=True)
    assert response.tool_calls[0]["args"] == {"city": "Tokyo"}
    assert response.metadata["usage"]["total_tokens"] == 5
    streamed = accumulate([chunk async for chunk in bot.stream([])])
    assert streamed.finish_reason == "tool_calls"
    assert streamed.tool_calls[0]["tool_name"] == "weather"
    assert bot.convert_message_for_api(response)["tool_calls"][0]["function"][
        "arguments"
    ] == {"city": "Tokyo"}
