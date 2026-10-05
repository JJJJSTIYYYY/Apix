"""Exercise MCP adaptation and batch lifetimes without external servers."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apix.agent.core.tool import Tool, ToolNode
from apix.agent.core.tool.mcp import MCPTool, MCPToolError, mcp_mgr
from apix.agent.core.utils.message import ApixAiMessage

META = {
    "mcp_id": "test-mcp",
    "mcp_name": "Test server",
    "transport": "http",
    "endpoint": "http://unused.invalid",
    "config": {"lifecycle": "tool_calls"},
}


def _mcp_tool(name):
    return MCPTool(
        SimpleNamespace(
            name=name, description="Test tool", inputSchema={"type": "object"}
        ),
        mcp_mgr,
        deepcopy(META),
        "tool_calls",
    )


def _state(*names):
    return {
        "messages": [
            ApixAiMessage(
                tool_calls=[
                    {"tool_name": name, "call_id": f"call-{index}", "args": {}}
                    for index, name in enumerate(names)
                ]
            )
        ]
    }


@pytest.mark.asyncio
async def test_mcp_tools_share_one_client_for_the_complete_batch(monkeypatch):
    calls = []
    closed = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append(True)

        async def call_tool(self, name, arguments, **kwargs):
            assert not closed
            calls.append(name)
            await asyncio.sleep(0)
            return {"content": [{"type": "text", "text": f"output:{name}"}]}

    create_client = AsyncMock(side_effect=lambda meta: Client())
    monkeypatch.setattr(mcp_mgr, "create_mcp_client", create_client)
    first, second = _mcp_tool("first"), _mcp_tool("second")
    assert isinstance(first, Tool)
    node = ToolNode([first, second], bind_llm_node="model")
    result = await node.execute(_state("first", "second", "first"))
    assert create_client.await_count == 1
    assert closed == [True]
    assert calls == ["first", "second", "first"]
    assert [m.content for m in result.update["messages"]] == [
        "output:first",
        "output:second",
        "output:first",
    ]
    assert result.goto == "model"

    closed.clear()
    await node.execute(_state("first"))
    assert create_client.await_count == 2
    assert closed == [True]


@pytest.mark.asyncio
async def test_mcp_failure_cleans_up_siblings_before_closing_client(monkeypatch):
    started = asyncio.Event()
    events = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            events.append("closed")

        async def call_tool(self, name, arguments, **kwargs):
            if name == "fail":
                await started.wait()
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": "failed"}],
                }
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                events.append("cancelled")

    monkeypatch.setattr(mcp_mgr, "create_mcp_client", AsyncMock(return_value=Client()))
    node = ToolNode([_mcp_tool("fail"), _mcp_tool("block")])
    with pytest.raises(MCPToolError, match="failed"):
        await asyncio.wait_for(node.execute(_state("fail", "block")), 1)
    assert events == ["cancelled", "closed"]
