import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI

from apix.agent.core.bot import Bot, InvocationPolicy
from apix.agent.core.utils.message import ApixUserMessage
from tests.agent.sdk.test_bot import weather


@pytest.mark.asyncio
async def test_openai_sdk_sends_single_built_request_and_vendor_extensions_as_json():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "c1",
                "object": "chat.completion",
                "created": 1,
                "model": "deepseek-v4",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AsyncOpenAI(
            api_key="test", base_url="https://example.test/v1", http_client=http
        )
        bot = Bot(
            provider="deepseek", model="deepseek-v4", api_key="test", client=client
        )
        response = await bot.invoke(
            [ApixUserMessage(content="hi")],
            tools=[weather],
            reasoning_effort="medium",
            request_options={"temperature": 0.2, "custom": {"value": 1}},
        )
        request = requests[0]
        payload = json.loads(request.content)
        assert str(request.url) == "https://example.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test"
        assert payload["thinking"] == {"type": "enabled"}
        assert payload["reasoning_effort"] == "high"
        assert payload["custom"] == {"value": 1}
        assert payload["tools"][0]["type"] == "function"
        assert "extra_body" not in payload
        assert response.content == "hello"
        await bot.aclose()
        assert not http.is_closed
        await client.close()


@pytest.mark.asyncio
async def test_responses_sdk_sends_stateless_context_and_parses_sse():
    requests = []

    async def handler(request):
        requests.append(request)
        body = (
            'data: {"type":"response.output_text.delta","delta":"hello","output_index":0,"content_index":0,"item_id":"m1","sequence_number":1}\n\n'
            'data: {"type":"response.completed","response":{"id":"r1","status":"completed","output":[],"usage":{"input_tokens":2,"output_tokens":3,"total_tokens":5}},"sequence_number":2}\n\n'
        )
        return httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http,
        AsyncOpenAI(
            api_key="test", base_url="https://example.test/v1", http_client=http
        ) as client,
    ):
        bot = Bot(provider="openai", model="gpt-5.2", api_key="test", client=client)
        chunks = [
            chunk
            async for chunk in bot.stream(
                [ApixUserMessage(content="hi")], tools=[weather]
            )
        ]
        assert chunks[0].content_delta == "hello"
        assert chunks[-1].finish_reason == "stop"
        payload = json.loads(requests[0].content)
        assert payload["store"] is False
        assert payload["input"] == [{"role": "user", "content": "hi"}]
        assert payload["tools"][0]["type"] == "function"
        assert "function" not in payload["tools"][0]
        assert "previous_response_id" not in payload


@pytest.mark.parametrize(
    "provider,model,path,header,response,input_key",
    [
        (
            "anthropic",
            "claude-sonnet-4-6",
            "/v1/messages",
            "x-api-key",
            {"content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn"},
            "messages",
        ),
        (
            "gemini",
            "gemini-3-pro",
            "/v1beta/models/gemini-3-pro:generateContent",
            "x-goog-api-key",
            {
                "candidates": [
                    {"content": {"parts": [{"text": "hi"}]}, "finishReason": "STOP"}
                ]
            },
            "contents",
        ),
        (
            "ollama",
            "qwen3",
            "/api/chat",
            "authorization",
            {"message": {"content": "hi"}, "done": True, "done_reason": "stop"},
            "messages",
        ),
    ],
)
@pytest.mark.asyncio
async def test_native_http_auth_routes_and_client_ownership(
    provider, model, path, header, response, input_key
):
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        bot = Bot(provider=provider, model=model, api_key="test", client=http)
        result = await bot.invoke([ApixUserMessage(content="hi")], tools=[weather])
        assert result.content == "hi"
        assert requests[0].url.path == path
        assert "test" in requests[0].headers[header]
        payload = json.loads(requests[0].content)
        assert input_key in payload
        assert "tools" in payload
        await bot.aclose()
        assert not http.is_closed


@pytest.mark.asyncio
async def test_native_sse_parser_supports_multiline_data_ping_and_final_no_newline():
    body = (
        ': keepalive\n\nevent: ping\ndata: {"type":"ping"}\n\n'
        'event: message_start\ndata: {"message":{"id":"m1","usage":{"input_tokens":2}}}\n\n'
        'event: content_block_start\ndata: {"index":0,"content_block":{"type":"text","text":""}}\n\n'
        'event: content_block_delta\ndata: {"index":0,\ndata: "delta":{"type":"text_delta","text":"hi"}}\n\n'
        'event: message_delta\ndata: {"delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}\n\n'
        "event: message_stop\ndata: {}"
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text=body, headers={"content-type": "text/event-stream"}
            )
        )
    ) as http:
        bot = Bot(
            provider="anthropic", model="claude-sonnet-4-6", api_key="test", client=http
        )
        chunks = [chunk async for chunk in bot.stream([])]
        assert "".join(chunk.content_delta for chunk in chunks) == "hi"
        assert chunks[-1].finish_reason == "stop"
        assert chunks[-1].metadata["usage"]["total_tokens"] == 3


@pytest.mark.asyncio
async def test_native_streams_ndjson_and_gemini_sse_use_correct_route():
    for provider, model, body in (
        (
            "ollama",
            "qwen3",
            '{"message":{"content":"hi"},"done":false}\n{"message":{},"done":true,"done_reason":"stop"}\n',
        ),
        (
            "gemini",
            "gemini-3-pro",
            'data: {"candidates":[{"content":{"parts":[{"text":"hi"}]},"finishReason":"STOP"}]}\n\n',
        ),
    ):
        requests = []

        def handler(request, requests=requests, body=body):
            requests.append(request)
            return httpx.Response(200, text=body)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            bot = Bot(provider=provider, model=model, api_key="test", client=http)
            chunks = [chunk async for chunk in bot.stream([])]
            assert chunks[0].content_delta == "hi"
            assert chunks[-1].finish_reason == "stop"
            if provider == "gemini":
                assert requests[0].url.params["alt"] == "sse"
                assert requests[0].url.path.endswith(":streamGenerateContent")


@pytest.mark.asyncio
async def test_http_retry_only_repeats_request_before_streaming(monkeypatch):
    calls = []
    sleeps = []

    async def no_wait(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("apix.agent.core.bot.protocol.base.asyncio.sleep", no_wait)

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429)
        if len(calls) == 2:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hi"}],
                "stop_reason": "end_turn",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        bot = Bot(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key="test",
            client=http,
            policy=InvocationPolicy(max_retries=2, timeout=10),
        )
        assert (await bot.invoke([])).content == "hi"
        assert len(calls) == 3
        assert sleeps == [0.5, 1]
        assert calls[0].content == calls[-1].content


@pytest.mark.asyncio
async def test_auth_errors_are_not_retried_and_sdk_requires_explicit_key():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": "unauthorized"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        bot = Bot(
            provider="anthropic", model="claude-sonnet-4-6", api_key="test", client=http
        )
        with pytest.raises(httpx.HTTPStatusError):
            await bot.invoke([])
        assert len(calls) == 1
    with pytest.raises(ValueError, match="explicitly"):
        Bot(provider="openai", model="gpt-5.2", api_key="")


@pytest.mark.asyncio
async def test_openai_sdk_transport_closes_stream_when_consumer_stops():
    closed = []

    class Stream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            return {"choices": [{"delta": {"content": "hi"}}]}

        async def close(self):
            closed.append(True)

    async def create(**request):
        return Stream()

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    bot = Bot(provider="deepseek", model="deepseek-v4", api_key="test", client=client)
    stream = bot.stream([])
    assert (await anext(stream)).content_delta == "hi"
    await stream.aclose()
    assert closed == [True]
