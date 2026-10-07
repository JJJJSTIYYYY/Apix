"""Opt-in paid provider tests; keys are supplied explicitly by the test runner."""

import os

import pytest
import pytest_asyncio

from apix.agent.core.bot import Bot, InvocationPolicy
from apix.agent.core.tool import tool
from apix.agent.core.utils.message import (
    ApixAiMessageAccumulator,
    ApixToolMessage,
    ApixUserMessage,
)

pytestmark = pytest.mark.skipif(
    not all(
        os.environ.get(name)
        for name in ("APIX_LIVE_PROVIDER", "APIX_LIVE_MODEL", "APIX_LIVE_API_KEY")
    ),
    reason="Set APIX_LIVE_PROVIDER, APIX_LIVE_MODEL and APIX_LIVE_API_KEY to enable paid integration tests",
)


@pytest_asyncio.fixture
async def live_bot():
    async with Bot(
        provider=os.environ["APIX_LIVE_PROVIDER"],
        model=os.environ["APIX_LIVE_MODEL"],
        endpoint=os.environ.get("APIX_LIVE_ENDPOINT"),
        api_key=os.environ["APIX_LIVE_API_KEY"],
        policy=InvocationPolicy(timeout=180, max_retries=1),
    ) as bot:
        yield bot


async def test_live_basic_chat_and_usage(live_bot):
    result = await live_bot.invoke([ApixUserMessage(content="Reply with exactly: OK")])
    assert result.content
    assert result.finish_reason == "stop"
    assert result.metadata["usage"]["total_tokens"] > 0


async def test_live_stream(live_bot):
    accumulator = ApixAiMessageAccumulator()
    async for chunk in live_bot.stream(
        [ApixUserMessage(content="Reply with exactly: OK")]
    ):
        accumulator.add(chunk)
    result = accumulator.to_message(require_finished=True)
    assert result.content
    assert result.metadata["usage"]["total_tokens"] > 0


@tool
def apix_test_lookup(token: str) -> str:
    """Resolve the test token by calling the Apix tool runtime."""
    return f"apix-local-result:{token}"


@pytest.mark.parametrize("stream", [False, True])
async def test_live_reasoning_function_call_and_history_replay(live_bot, stream):
    if not live_bot.model_profile.tools.supported:
        pytest.skip("model does not support function tools")
    prompt = ApixUserMessage(
        content=(
            "Call apix_test_lookup once with token='abc123' before answering. "
            "Do not guess its result. After the tool returns, repeat the result exactly."
        )
    )
    messages = [prompt]
    if stream:
        accumulator = ApixAiMessageAccumulator()
        async for chunk in live_bot.stream(messages, tools=[apix_test_lookup]):
            accumulator.add(chunk)
        first = accumulator.to_message(require_finished=True)
    else:
        first = await live_bot.invoke(messages, tools=[apix_test_lookup])
    assert len(first.tool_calls) == 1
    assert first.tool_calls[0]["tool_name"] == "apix_test_lookup"
    output = await apix_test_lookup.func(**first.tool_calls[0]["args"])
    messages.extend(
        [
            first,
            ApixToolMessage(
                tool_call_id=first.tool_calls[0]["call_id"], content=output
            ),
        ]
    )
    result = await live_bot.invoke(messages, tools=[])
    assert output in result.content
