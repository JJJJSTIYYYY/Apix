"""Actual SDK transport tests through the library; no Apix codec or client injection."""
import json

import httpx
import pytest
from anthropic import AsyncAnthropic
from google import genai
from ollama import AsyncClient as AsyncOllama
from openai import AsyncOpenAI
from my_llm import IncompleteStreamError, ModelProfile, ProviderProfile

from apix.agent.core.bot import ApixBot
from apix.agent.core.utils.message import ApixAiMessage, ApixUserMessage
from apix.agent.core.tool import ToolNode
from tests.agent.sdk.test_bot import weather

GenAIClient = genai.Client


def wire(protocol):
    if protocol == "openai_chat":
        events = [{"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
                   "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": "stop"}]}]
    elif protocol == "openai_responses":
        events = [{"type": "response.completed", "sequence_number": 1, "response": {
            "id": "r", "status": "completed", "output": [{"type": "message", "id": "m",
            "role": "assistant", "status": "completed", "content": [
                {"type": "output_text", "text": "hello", "annotations": []}]}]}}]
    elif protocol == "anthropic":
        events = [
            {"type": "message_start", "message": {"id": "m", "type": "message", "role": "assistant",
             "model": "test", "content": [], "stop_reason": None, "usage": {"input_tokens": 1, "output_tokens": 0}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hello"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 1}},
            {"type": "message_stop"},
        ]
    elif protocol == "gemini":
        events = [{"candidates": [{"content": {"role": "model", "parts": [{"text": "hello"}]}, "finishReason": "STOP"}]}]
    else:
        return json.dumps({"model": "test", "message": {"role": "assistant", "content": "hello"}, "done": True, "done_reason": "stop"}) + "\n"
    return "".join((f"event: {e['type']}\n" if "type" in e else "") + f"data: {json.dumps(e)}\n\n" for e in events)


def install_sdk(monkeypatch, protocol, handler):
    clients = []
    def openai_factory(**kwargs):
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler)); clients.append(http)
        return AsyncOpenAI(**kwargs, http_client=http)
    def anthropic_factory(**kwargs):
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler)); clients.append(http)
        return AsyncAnthropic(**kwargs, http_client=http)
    def gemini_factory(**kwargs):
        options = kwargs.pop("http_options")
        options = options.model_copy(update={"async_client_args": {
            **(options.async_client_args or {}), "transport": httpx.MockTransport(handler)}})
        client = GenAIClient(**kwargs, http_options=options)
        clients.append(client._api_client._async_httpx_client)
        return client
    def ollama_factory(**kwargs):
        client = AsyncOllama(**kwargs, transport=httpx.MockTransport(handler)); clients.append(client._client)
        return client
    module, name, factory = {
        "openai_chat": ("openai.chat", "AsyncOpenAI", openai_factory),
        "openai_responses": ("openai.responses", "AsyncOpenAI", openai_factory),
        "anthropic": ("anthropic", "AsyncAnthropic", anthropic_factory),
        "gemini": ("gemini", "genai.Client", gemini_factory),
        "ollama": ("ollama", "AsyncOllama", ollama_factory),
    }[protocol]
    monkeypatch.setattr(f"my_llm.codec.{module}.decoding.request.transport.{name}", factory)
    return clients


@pytest.mark.parametrize("protocol", ["openai_chat", "openai_responses", "anthropic", "gemini", "ollama"])
@pytest.mark.parametrize("streaming", [False, True])
async def test_sdk_protocols_keep_chat_input_and_output(monkeypatch, protocol, streaming):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=wire(protocol), headers={"content-type":
            "application/x-ndjson" if protocol == "ollama" else "text/event-stream"})
    clients = install_sdk(monkeypatch, protocol, handler)
    bot = ApixBot(provider=ProviderProfile(protocol=protocol, api_key="test", base_url="https://local.test"),
                  model=ModelProfile(model="test", max_tokens=100, supports_function_calling=True))
    messages = [ApixUserMessage(content="hi")]
    if streaming:
        stream = await bot.stream(messages, tools=[] if protocol == "ollama" else [weather])
        async with stream:
            events = [event async for event in stream]
        assert all("choices" in event for event in events)
        result = ApixAiMessage.from_chat(stream.result)
    else:
        result = await bot.invoke(messages, tools=[] if protocol == "ollama" else [weather])
    assert result.content == "hello"
    assert all(client.is_closed for client in clients)
    body = json.loads(requests[0].content)
    assert "hi" in str(body)
    if protocol != "ollama":
        assert "weather" in str(body)
    assert "message_uid" not in str(body) and "extensions" not in str(body)


async def test_sdk_tool_round_trip_is_standard_and_executable(monkeypatch):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        delta = {"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {
            "name": "weather", "arguments": '{"city":"Tokyo"}'}}]} if len(calls) == 1 else {"content": "sunny"}
        event = {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
                 "choices": [{"index": 0, "delta": delta, "finish_reason": "tool_calls" if len(calls) == 1 else "stop"}]}
        return httpx.Response(200, text=f"data: {json.dumps(event)}\n\n", headers={"content-type": "text/event-stream"})
    clients = install_sdk(monkeypatch, "openai_chat", handler)
    bot = ApixBot(provider=ProviderProfile(api_key="test"), model=ModelProfile(model="test", supports_function_calling=True)).bind_tools([weather])
    prompt = ApixUserMessage(content="weather?")
    first = await bot.invoke([prompt])
    output = await ToolNode(weather).execute({"messages": [first]})
    tool_result = output.update["messages"][0]
    assert tool_result.content == "sunny in Tokyo"
    assert tool_result.to_chat()["tool_call_id"] == "c1"
    final = await bot.invoke([prompt, first, tool_result])
    assert final.content == "sunny"
    assert json.loads(calls[1]["messages"][1]["tool_calls"][0]["function"]["arguments"]) == {"city": "Tokyo"}
    assert all(client.is_closed for client in clients)


async def test_early_exit_and_missing_terminal_close_owned_sdk_clients(monkeypatch):
    event = {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
             "choices": [{"index": 0, "delta": {"content": "partial"}, "finish_reason": None}]}
    def handler(request):
        return httpx.Response(200, text=f"data: {json.dumps(event)}\n\n", headers={"content-type": "text/event-stream"})
    clients = install_sdk(monkeypatch, "openai_chat", handler)
    bot = ApixBot(provider=ProviderProfile(api_key="test"), model=ModelProfile(model="test"))
    stream = await bot.stream([{"role": "user", "content": "hi"}])
    async with stream:
        await anext(stream)
    assert clients[-1].is_closed
    with pytest.raises(IncompleteStreamError):
        await bot.invoke([{"role": "user", "content": "hi"}])
    assert clients[-1].is_closed


async def test_cancelling_one_request_closes_its_body_and_preserves_concurrent_stream(monkeypatch):
    import asyncio

    release = asyncio.Event()
    ready = asyncio.Barrier(3)
    bodies = {}

    class Body(httpx.AsyncByteStream):
        def __init__(self, label):
            self.label = label
            self.closed = False

        async def __aiter__(self):
            for delta, finish in (({"content": self.label}, None), ({}, "stop")):
                if finish:
                    await release.wait()
                event = {"id": self.label, "object": "chat.completion.chunk", "created": 1,
                         "model": "test", "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                yield f"data: {json.dumps(event)}\n\n".encode()

        async def aclose(self):
            self.closed = True

    def handler(request):
        label = json.loads(request.content)["messages"][0]["content"]
        body = bodies[label] = Body(label)
        return httpx.Response(200, stream=body, headers={"content-type": "text/event-stream"})

    clients = install_sdk(monkeypatch, "openai_chat", handler)
    bot = ApixBot(provider=ProviderProfile(api_key="test"), model=ModelProfile(model="test"))

    async def consume(label):
        stream = await bot.stream([{"role": "user", "content": label}])
        async with stream:
            async for event in stream:
                if any(choice["delta"].get("content") for choice in event["choices"]):
                    await ready.wait()
        return stream.result

    first = asyncio.create_task(consume("first"))
    second = asyncio.create_task(consume("second"))
    try:
        await asyncio.wait_for(ready.wait(), 3)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert bodies["first"].closed
        assert not bodies["second"].closed
        release.set()
        assert (await asyncio.wait_for(second, 3))["content"] == "second"
        assert bodies["second"].closed
        assert all(client.is_closed for client in clients)
    finally:
        for task in (first, second):
            if not task.done():
                task.cancel()
        await asyncio.gather(first, second, return_exceptions=True)


async def test_ollama_schema_constraint_rejection_is_not_silently_weakened():
    from my_llm import UnsupportedCapabilityError

    bot = ApixBot(provider=ProviderProfile(protocol="ollama"),
                  model=ModelProfile(model="test", supports_function_calling=True))
    with pytest.raises(UnsupportedCapabilityError, match="schema constraints"):
        await bot.invoke([{"role": "user", "content": "hi"}], tools=[weather])
