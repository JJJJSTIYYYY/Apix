"""Shared types and lifecycle primitives for the FastMCP integration."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from fastmcp import Client


if TYPE_CHECKING:
    from apix.agent.sdk.tool.mcp.mcp_tool_manager import MCPToolManager


MCPLifecycle = Literal["keep_alive", "agent_invoke", "tool_calls"]
MCPTransport = Literal[
    "stdio",
    "http",
    "streamable_http",
    "websocket",
    "sse",
]


class McpMetaSchema(TypedDict):
    """Stored configuration for one MCP server."""

    mcp_id: str
    mcp_name: str
    transport: MCPTransport
    # For stdio this may be the command. For network transports it is the URL.
    endpoint: str
    config: dict[str, Any]


class MCPToolError(RuntimeError):
    """Raised when an MCP server returns a failed tool result."""


def _get_model_value(model: Any, *names: str, default: Any = None) -> Any:
    """Read the first available Python or wire-format model attribute."""
    for name in names:
        if isinstance(model, Mapping) and name in model:
            return model[name]
        if hasattr(model, name):
            return getattr(model, name)
    return default


def _dump_content_block(content: Any) -> str:
    """Serialize a non-text MCP content block without losing its metadata."""
    if hasattr(content, "model_dump"):
        value = content.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )
    elif isinstance(content, Mapping):
        value = dict(content)
    else:
        return str(content)
    return json.dumps(value, ensure_ascii=False, default=str)


def _convert_call_tool_result(result: Any) -> str:
    """Convert a FastMCP call result into model-readable text."""
    output_parts: list[str] = []
    for content in _get_model_value(result, "content", default=[]) or []:
        if _get_model_value(content, "type") == "text":
            output_parts.append(
                str(_get_model_value(content, "text", default=""))
            )
        else:
            output_parts.append(_dump_content_block(content))

    structured_content = _get_model_value(
        result,
        "structured_content",
        "structuredContent",
    )
    if not output_parts and structured_content is not None:
        output_parts.append(
            json.dumps(
                structured_content,
                ensure_ascii=False,
                default=str,
            )
        )

    data = _get_model_value(result, "data")
    if not output_parts and data is not None:
        if isinstance(data, str):
            output_parts.append(data)
        else:
            output_parts.append(
                json.dumps(data, ensure_ascii=False, default=str)
            )

    output = "\n".join(output_parts)
    if _get_model_value(result, "is_error", "isError", default=False):
        raise MCPToolError(output or "MCP tool execution failed.")
    return output


def _meta_signature(mcp_meta: McpMetaSchema) -> str:
    """Return a stable signature used to reject stale scoped clients."""
    return json.dumps(
        mcp_meta,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


@dataclass(slots=True)
class _MCPClientEntry:
    """One entered FastMCP client and the configuration that created it."""

    client: Client
    signature: str


class _MCPClientScope:
    """Own entered FastMCP clients for one APIX lifecycle scope."""

    def __init__(self, manager: MCPToolManager) -> None:
        self._manager = manager
        self._entries: dict[str, _MCPClientEntry] = {}
        self._lock = asyncio.Lock()

    @property
    def clients(self) -> dict[str, Client]:
        """Return a snapshot of clients currently owned by this scope."""
        return {
            mcp_id: entry.client
            for mcp_id, entry in self._entries.items()
        }

    async def get_client(self, mcp_meta: McpMetaSchema) -> Client:
        """Return the matching entered client, replacing stale entries."""
        mcp_id = mcp_meta["mcp_id"]
        signature = _meta_signature(mcp_meta)

        async with self._lock:
            entry = self._entries.get(mcp_id)
            if entry is not None and entry.signature == signature:
                return entry.client

            if entry is not None:
                self._entries.pop(mcp_id, None)
                await entry.client.__aexit__(None, None, None)

            client = await self._manager.create_mcp_client(mcp_meta)
            if client is None:
                raise RuntimeError(
                    f"Unable to create MCP client {mcp_meta['mcp_name']!r}."
                )

            await client.__aenter__()
            self._entries[mcp_id] = _MCPClientEntry(
                client=client,
                signature=signature,
            )
            return client

    async def close(self) -> None:
        """Exit every owned client in reverse creation order."""
        async with self._lock:
            entries = list(reversed(self._entries.values()))
            self._entries.clear()

        first_error: BaseException | None = None
        for entry in entries:
            try:
                await entry.client.__aexit__(None, None, None)
            except BaseException as exc:
                if first_error is None:
                    first_error = exc

        if first_error is not None:
            raise first_error


_current_tool_calls_scope: ContextVar[_MCPClientScope | None] = ContextVar(
    "apix_mcp_tool_calls_scope",
    default=None,
)


__all__ = [
    "MCPLifecycle",
    "MCPToolError",
    "MCPTransport",
    "McpMetaSchema",
]
