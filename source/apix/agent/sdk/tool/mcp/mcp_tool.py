"""Adapt FastMCP tool definitions to APIX tools."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from apix.agent.sdk.tool.mcp.base import (
    MCPLifecycle,
    McpMetaSchema,
    _convert_call_tool_result,
    _get_model_value,
)
from apix.agent.sdk.tool.tool_node import Tool
from apix.agent.sdk.utils.message import ToolCall


if TYPE_CHECKING:
    from apix.agent.sdk.tool.mcp.mcp_tool_manager import MCPToolManager


class MCPTool(Tool):
    """Adapt one FastMCP tool definition to APIX's ``Tool`` contract."""

    def __init__(
        self,
        definition: Any,
        manager: MCPToolManager,
        mcp_meta: McpMetaSchema,
        lifecycle: MCPLifecycle,
    ) -> None:
        name = _get_model_value(definition, "name")
        if not isinstance(name, str) or not name:
            raise ValueError("An MCP tool requires a non-empty name.")

        description = _get_model_value(definition, "description")
        if not description:
            description = _get_model_value(definition, "title", default="")

        input_schema = _get_model_value(
            definition,
            "input_schema",
            "inputSchema",
            default={},
        )
        if not isinstance(input_schema, Mapping):
            raise TypeError(
                f"MCP tool {name!r} input schema must be a mapping."
            )

        self.name = name
        self.description = str(description or "")
        self.mcp_id = mcp_meta["mcp_id"]
        self.mcp_name = mcp_meta["mcp_name"]
        self.lifecycle = lifecycle
        self._manager = manager
        self._mcp_meta = deepcopy(mcp_meta)
        self.func = self._call
        self.schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": deepcopy(dict(input_schema)),
            },
        }

    @asynccontextmanager
    async def tool_call_batch_context(self) -> AsyncGenerator[None]:
        """Keep the configured client scope active for one ToolNode batch."""
        async with self._manager.client_scope(
            self._mcp_meta,
            self.lifecycle,
        ):
            yield

    async def _call(self, **arguments: Any) -> str:
        async with self._manager.client_scope(
            self._mcp_meta,
            self.lifecycle,
        ) as client:
            result = await client.call_tool(
                self.name,
                arguments,
                raise_on_error=False,
            )
        return _convert_call_tool_result(result)

    async def execute(
        self,
        state: dict[str, Any],
        tool_call: ToolCall,
    ) -> str:
        """Call the FastMCP tool with arguments supplied by the model."""
        if not isinstance(state, dict):
            raise TypeError("state must be a dictionary.")

        self._validate_tool_call(tool_call)
        if tool_call["tool_name"] != self.name:
            raise ValueError(
                f"ToolCall targets {tool_call['tool_name']!r}, "
                f"but this tool is {self.name!r}."
            )

        return await self._call(**(tool_call["args"] or {}))


__all__ = ["MCPTool"]
