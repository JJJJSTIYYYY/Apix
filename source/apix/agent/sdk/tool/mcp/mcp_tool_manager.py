"""FastMCP client creation and APIX lifecycle scope management."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import (
    SSETransport,
    StdioTransport,
    StreamableHttpTransport,
)

from apix.agent.sdk.tool.mcp.base import (
    MCPLifecycle,
    McpMetaSchema,
    _current_tool_calls_scope,
    _MCPClientScope,
)
from apix.agent.sdk.tool.mcp.mcp_tool import MCPTool
from apix.agent.store import query_store
from apix.common.lifespan import auto_init
from apix.common.utils import logger
from apix.core.graph.context import get_current_run_id


class MCPToolManager:
    """Create FastMCP clients and apply APIX lifecycle scopes."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._keep_alive_scope = _MCPClientScope(self)
        self._agent_scopes: dict[str, _MCPClientScope] = {}
        self._agent_scopes_lock = asyncio.Lock()

    @property
    def keep_alive_clients(self) -> dict[str, Client]:
        """Return clients retained for the lifetime of the process."""
        return self._keep_alive_scope.clients

    async def get_mcp_meta(
        self,
        user_uid: str,
    ) -> list[McpMetaSchema]:
        try:
            res = await query_store(
                action="get_enabled_mcp_servers",
                payload={"user_uid": user_uid},
            )
            return res.get("messages", [])
        except Exception as exc:
            logger.warning(f"Failed to fetch MCP meta: {exc}")
            return []

    @staticmethod
    def _resolve_endpoint(
        mcp_meta: McpMetaSchema,
        config_key: str,
    ) -> str:
        config = mcp_meta.get("config", {})
        value = config.get(config_key) or mcp_meta.get("endpoint")
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"MCP {mcp_meta.get('mcp_name')!r} requires a non-empty "
                f"{config_key}."
            )
        return value

    @staticmethod
    def resolve_lifecycle(mcp_meta: McpMetaSchema) -> MCPLifecycle:
        """Return the validated APIX lifecycle configured for one server."""
        lifecycle = (
            mcp_meta.get("config", {}).get("lifecycle", "keep_alive")
            or "keep_alive"
        )
        if lifecycle not in {"keep_alive", "agent_invoke", "tool_calls"}:
            raise ValueError(
                f"Unknown lifecycle {lifecycle!r} for MCP "
                f"{mcp_meta.get('mcp_name')!r}. Expected one of: "
                "'keep_alive', 'agent_invoke', 'tool_calls'."
            )
        return lifecycle

    async def create_mcp_client(
        self,
        mcp_meta: McpMetaSchema,
    ) -> Client | None:
        """Build an unentered FastMCP client for one configured server."""
        transport_name = mcp_meta["transport"]
        mcp_name = mcp_meta["mcp_name"]
        config = mcp_meta.get("config", {})
        lifecycle = self.resolve_lifecycle(mcp_meta)

        try:
            transport_options = dict(config.get("transport_kwargs", {}))
            if transport_name == "stdio":
                transport_options.update(
                    command=self._resolve_endpoint(mcp_meta, "command"),
                    args=list(config.get("args", [])),
                    env=config.get("env") or None,
                    cwd=config.get("cwd"),
                    keep_alive=lifecycle == "keep_alive",
                )
                transport = StdioTransport(**transport_options)
            elif transport_name in {"http", "streamable_http", "sse"}:
                transport_options.update(
                    url=self._resolve_endpoint(mcp_meta, "url"),
                    headers=dict(config.get("headers", {})),
                )
                for option in ("auth", "sse_read_timeout", "verify"):
                    if option in config:
                        transport_options[option] = config[option]

                transport_type = (
                    SSETransport
                    if transport_name == "sse"
                    else StreamableHttpTransport
                )
                transport = transport_type(**transport_options)
            elif transport_name == "websocket":
                logger.warning(
                    "FastMCP no longer supports the deprecated websocket "
                    f"transport for {mcp_name!r}."
                )
                return None
            else:
                logger.warning(
                    f"Unknown transport {transport_name!r} for MCP "
                    f"{mcp_name!r}."
                )
                return None

            client_options = dict(config.get("session_kwargs", {}))
            client_options.update(config.get("client_kwargs", {}))
            for option in (
                "auto_initialize",
                "init_timeout",
                "timeout",
            ):
                if option in config:
                    client_options[option] = config[option]

            client = Client(transport, **client_options)
            logger.info(f"Created FastMCP client: {mcp_name}")
            return client
        except Exception as exc:
            logger.error(f"Error while creating MCP client: {exc}")
            return None

    async def _get_agent_scope(self, run_id: str) -> _MCPClientScope:
        """Return the client scope owned by one AgentGraph invocation."""
        async with self._agent_scopes_lock:
            scope = self._agent_scopes.get(run_id)
            if scope is None:
                scope = _MCPClientScope(self)
                self._agent_scopes[run_id] = scope
            return scope

    @asynccontextmanager
    async def client_scope(
        self,
        mcp_meta: McpMetaSchema,
        lifecycle: MCPLifecycle,
    ) -> AsyncGenerator[Client]:
        """Acquire a client using the configured APIX lifecycle boundary."""
        if lifecycle == "keep_alive":
            yield await self._keep_alive_scope.get_client(mcp_meta)
            return

        if lifecycle == "agent_invoke":
            try:
                run_id = get_current_run_id()
            except RuntimeError as exc:
                raise RuntimeError(
                    "The 'agent_invoke' MCP lifecycle requires execution "
                    "inside an AgentGraph invocation."
                ) from exc
            scope = await self._get_agent_scope(run_id)
            yield await scope.get_client(mcp_meta)
            return

        current_scope = _current_tool_calls_scope.get()
        owns_scope = current_scope is None
        token = None
        scope = current_scope
        if scope is None:
            scope = _MCPClientScope(self)
            token = _current_tool_calls_scope.set(scope)

        try:
            yield await scope.get_client(mcp_meta)
        finally:
            if owns_scope:
                try:
                    await scope.close()
                finally:
                    assert token is not None
                    _current_tool_calls_scope.reset(token)

    async def close_agent_scope(self, run_id: str) -> None:
        """Close every client owned by one completed AgentGraph invocation."""
        async with self._agent_scopes_lock:
            scope = self._agent_scopes.pop(run_id, None)
        if scope is not None:
            await scope.close()

    async def _list_temporary_tools(
        self,
        mcp_meta: McpMetaSchema,
    ) -> list[Any]:
        """Discover tools through a client that closes after discovery."""
        client = await self.create_mcp_client(mcp_meta)
        if client is None:
            return []
        async with client:
            return list(await client.list_tools())

    async def get_mcp_tools(
        self,
        mcp_meta: McpMetaSchema,
    ) -> list[MCPTool]:
        """Load APIX tools using the configured FastMCP lifecycle."""
        mcp_name = mcp_meta["mcp_name"]
        try:
            lifecycle = self.resolve_lifecycle(mcp_meta)
            if lifecycle == "keep_alive":
                client = await self._keep_alive_scope.get_client(mcp_meta)
                definitions = list(await client.list_tools())
            else:
                definitions = await self._list_temporary_tools(mcp_meta)

            tools = [
                MCPTool(
                    definition,
                    self,
                    mcp_meta,
                    lifecycle,
                )
                for definition in definitions
            ]
            logger.info(f"Loaded {len(tools)} MCP tools for {mcp_name!r}")
            return tools
        except Exception as exc:
            logger.error(f"Error while getting MCP tools: {exc}")
            return []

    async def load_all_mcp_tools(
        self,
        user_uid: str,
    ) -> list[MCPTool]:
        """Load tools from every enabled MCP server for one user."""
        all_tools: list[MCPTool] = []
        for mcp_meta in await self.get_mcp_meta(user_uid):
            all_tools.extend(await self.get_mcp_tools(mcp_meta))
        return all_tools

    async def cleanup_all(self) -> None:
        """Close every keep-alive and in-flight Agent-scoped client."""
        async with self._agent_scopes_lock:
            agent_scopes = list(self._agent_scopes.values())
            self._agent_scopes.clear()

        scopes = [*agent_scopes, self._keep_alive_scope]
        for scope in scopes:
            try:
                await scope.close()
            except Exception as exc:
                logger.error(f"Error while cleaning MCP clients: {exc}")

    async def start(self) -> None:
        """MCP clients are opened lazily when their tools are requested."""

    async def stop(self) -> None:
        await self.cleanup_all()


mcp_mgr = MCPToolManager()

auto_init.register(mcp_mgr)


__all__ = [
    "MCPToolManager",
    "mcp_mgr",
]
