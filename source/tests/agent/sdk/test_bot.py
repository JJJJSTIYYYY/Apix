"""Apix application responsibilities around the library's standard Chat API."""
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from my_llm import ModelProfile, ProviderProfile

from apix.agent.core.bot import ApixBot
from apix.agent.core.tool import ToolNode, tool
from apix.agent.core.utils.message import ApixAiMessage, ApixSystemMessage, ApixUserMessage


@tool
def weather(city: str) -> str:
    """Get weather for a city."""
    return f"sunny in {city}"


def make_bot(**kwargs):
    return ApixBot(provider=ProviderProfile(api_key="test"),
                   model=ModelProfile(model="test", supports_function_calling=True), **kwargs)


def test_profiles_are_library_types_and_stdio_is_explicit():
    bot = make_bot()
    assert bot.llm.stdio_protocol == "openai_chat"
    assert bot.model.model == "test"
    assert isinstance(bot.provider, ProviderProfile)


def test_tool_binding_filters_copies_replaces_and_rejects_duplicate_names():
    bot = make_bot()
    assert bot.bind_tools([weather]) is bot
    schemas = bot.tool_schemas
    schemas[0]["function"]["name"] = "changed"
    assert bot.tool_schemas == [weather.get_schema()]
    bot.bind_tools(ToolNode(weather), tool_permission_set=set())
    assert bot.tool_schemas == []
    with pytest.raises(ValueError, match="unique"):
        bot.bind_tools([weather, weather])
    for invalid in ([object()], "weather", 12, {}):
        with pytest.raises(TypeError):
            bot.bind_tools(invalid)


@pytest.mark.asyncio
async def test_invoke_orders_context_and_delegates_standard_messages_and_options(monkeypatch):
    role = {"name": " Alice ", "definition": "Be concise", "title": None}
    bot = make_bot(role_schema=role).bind_tools([weather])
    role["name"] = "changed"
    assert bot.name == "Alice"
    call = {"id": "c1", "type": "function", "function": {
        "name": "weather", "arguments": '{"city":"Tokyo"}'}}
    response = {"role": "assistant", "content": None, "tool_calls": [call], "reasoning_content": "why"}
    generate = AsyncMock(return_value=deepcopy(response))
    monkeypatch.setattr(bot.llm, "generate", generate)
    result = await bot.invoke([ApixUserMessage(content="weather", extensions={"active_file": "notes"})],
                              [ApixSystemMessage(content="global")], reasoning=True, max_tokens=40)
    sent = generate.await_args.kwargs
    assert sent["messages"][0] == {"role": "system", "content": "global"}
    assert "Your name: Alice" in sent["messages"][1]["content"]
    assert sent["messages"][2] == {"role": "user", "content": "weather"}
    assert sent["tools"] == [weather.get_schema()]
    assert sent["reasoning"] is True and sent["max_tokens"] == 40
    assert isinstance(result, ApixAiMessage)
    assert result.tool_calls == [call]
    assert result.reasoning_content == "why"
    assert result.extensions == {}
    await bot.invoke([{"role": "user", "content": "hi"}], tools=[])
    assert generate.await_args.kwargs["tools"] == []
    assert bot.tool_schemas


@pytest.mark.asyncio
async def test_stream_returns_library_object_without_wrapping(monkeypatch):
    bot = make_bot()
    stream = object()
    generate = AsyncMock(return_value=stream)
    monkeypatch.setattr(bot.llm, "generate", generate)
    assert await bot.stream([{"role": "user", "content": "hi"}]) is stream
    assert generate.await_args.kwargs["stream"] is True


def test_input_and_role_validation():
    bot = make_bot()
    with pytest.raises(TypeError):
        bot._messages((), None)
    with pytest.raises(TypeError):
        bot._messages([], ())
    for role in ({}, {"name": "x", "definition": "x", "title": 1}):
        with pytest.raises(TypeError):
            bot.bind_role_schema(role)
