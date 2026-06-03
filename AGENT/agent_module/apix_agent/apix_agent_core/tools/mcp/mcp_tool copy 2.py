import asyncio
from contextlib import _AsyncGeneratorContextManager

import httpx
from langchain_mcp_adapters.client import (
    MultiServerMCPClient,
    SSEConnection,
    StdioConnection,
    StreamableHttpConnection,
    WebsocketConnection,
)
from langchain_core.tools.base import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools

from apix_agent.commons.auto_init import auto_init
from apix_agent.commons.logger import logger
from apix_agent.global_config import MEMORY_SERVICE_BASE_URL
from apix_agent.commons.type_def import McpMetaSchema


class MCPContextHolder:

    def __init__(
        self,
        mcp_id: str,
        mcp_name: str,
        lifecycle: str,
        cm: _AsyncGeneratorContextManager,
    ):
        self.mcp_id = mcp_id
        self.mcp_name = mcp_name
        self.lifecycle = lifecycle

        self.cm = cm

        self.session = None
        self.tools: list[BaseTool] | None = None

        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    async def start(self):
        if self._worker_task:
            return

        loop = asyncio.get_running_loop()
        ready = loop.create_future()

        self._worker_task = asyncio.create_task(
            self._run(ready),
            name=f"mcp-lifecycle-{self.mcp_name}",
        )

        await ready

    async def _run(self, ready_future: asyncio.Future):
        try:
            self.session = await self.cm.__aenter__()

            if not ready_future.done():
                ready_future.set_result(True)

            while True:
                action, future = await self._queue.get()

                if action == "close":
                    try:
                        await self.cm.__aexit__(None, None, None)

                        if not future.done():
                            future.set_result(True)

                    except Exception as e:
                        if not future.done():
                            future.set_exception(e)

                    break

        except Exception as e:
            if not ready_future.done():
                ready_future.set_exception(e)

            raise

        finally:
            self.session = None
            self.tools = None

    async def stop(self):
        if not self._worker_task:
            return

        if self._worker_task.done():
            try:
                await self._worker_task
            except Exception as e:
                logger.error(
                    f"[MCPContextHolder.stop] "
                    f"Worker already failed for '{self.mcp_name}': {e}"
                )
            finally:
                self._worker_task = None
                self.session = None
                self.tools = None

            return

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        await self._queue.put(("close", future))

        await future

        try:
            await self._worker_task
        finally:
            self._worker_task = None
            self.session = None
            self.tools = None

    async def get_tools(self) -> list[BaseTool]:
        if self.tools is None:
            self.tools = await load_mcp_tools(self.session)

        return self.tools


class MCPToolManager:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        self.mcp_client_cm: dict[str, MCPContextHolder] = {}

    async def get_mcp_meta(
        self,
        client_id: str,
    ) -> list[McpMetaSchema]:

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/mcp/get_enabled_mcp_servers",
                json={
                    "client_id": client_id,
                },
            )

        res = resp.json()

        if resp.status_code != 200 or not res.get("success"):
            logger.warning(
                "[get_mcp_meta] Failed to get MCP meta: "
                f"{resp.text}"
            )
            return []

        return res.get("messages", [])

    async def create_mcp_client(
        self,
        mcp_meta: McpMetaSchema,
    ) -> MultiServerMCPClient | None:

        transport = mcp_meta["transport"]
        mcp_name = mcp_meta["mcp_name"]
        config = mcp_meta.get("config", {})

        try:

            if transport == "stdio":

                connection: StdioConnection = {
                    mcp_name: {
                        "transport": "stdio",
                        "command": config.get("command"),
                        "args": config.get("args", []),
                        "env": config.get("env", {}),
                        "cwd": config.get("cwd"),
                        "encoding": config.get(
                            "encoding",
                            "utf-8",
                        ),
                        "session_kwargs": config.get(
                            "session_kwargs",
                            {},
                        ),
                    }
                }

            elif transport == "streamable_http":

                connection: StreamableHttpConnection = {
                    mcp_name: {
                        "transport": "streamable_http",
                        "url": config.get("url"),
                        "headers": config.get(
                            "headers",
                            {},
                        ),
                        "timeout": 30,
                        "sse_read_timeout": 30,
                        "terminate_on_close": True,
                        "session_kwargs": config.get(
                            "session_kwargs",
                            {},
                        ),
                    }
                }

            elif transport == "websocket":

                connection: WebsocketConnection = {
                    mcp_name: {
                        "transport": "websocket",
                        "url": config.get("url"),
                        "session_kwargs": config.get(
                            "session_kwargs",
                            {},
                        ),
                    }
                }

            elif transport == "sse":

                connection: SSEConnection = {
                    mcp_name: {
                        "transport": "sse",
                        "url": config.get("url"),
                        "headers": config.get(
                            "headers",
                            {},
                        ),
                        "timeout": 30,
                        "sse_read_timeout": 30,
                        "session_kwargs": config.get(
                            "session_kwargs",
                            {},
                        ),
                    }
                }

            else:
                logger.warning(
                    f"[create_mcp_client] Unknown transport "
                    f"'{transport}' for MCP '{mcp_name}'."
                )
                return None

            client = MultiServerMCPClient(connection)

            logger.info(
                f"[create_mcp_client] Created MCP client: "
                f"{mcp_name}"
            )

            return client

        except Exception as e:
            logger.error(
                f"[create_mcp_client] Error while creating "
                f"MCP client: {e}"
            )
            return None

    async def get_mcp_tools(
        self,
        mcp_meta: McpMetaSchema,
    ) -> list[BaseTool]:

        mcp_id = mcp_meta["mcp_id"]
        mcp_name = mcp_meta["mcp_name"]

        config = mcp_meta.get("config", {})
        lifecycle = (
            config.get("lifecycle", "keep_alive")
            or "keep_alive"
        )

        try:

            if lifecycle in (
                "keep_alive",
                "agent_loop",
            ):

                client = await self.create_mcp_client(
                    mcp_meta
                )

                if not client:
                    return []

                cm = client.session(mcp_name)

                holder = MCPContextHolder(
                    mcp_id=mcp_id,
                    mcp_name=mcp_name,
                    lifecycle=lifecycle,
                    cm=cm,
                )

                await holder.start()

                self.mcp_client_cm[mcp_id] = holder

                tools = await holder.get_tools()

                logger.info(
                    f"[get_mcp_tools] Loaded "
                    f"{len(tools)} MCP tools "
                    f"for '{mcp_name}'"
                )

                return tools

            elif lifecycle == "always_close":

                client = await self.create_mcp_client(
                    mcp_meta
                )

                if not client:
                    return []

                return await client.get_tools()

            logger.warning(
                f"[get_mcp_tools] Unknown lifecycle "
                f"'{lifecycle}' for MCP '{mcp_name}'."
            )

            return []

        except Exception as e:
            logger.error(
                f"[get_mcp_tools] Error while "
                f"getting MCP tools: {e}"
            )
            return []

    async def cache_first(
        self,
        mcp_meta: McpMetaSchema,
    ) -> list[BaseTool] | None:
        logger.trace(f'[mcp_tool.py] [MCPToolManager] [cache_first] Enter')

        mcp_id = mcp_meta["mcp_id"]

        lifecycle = (
            mcp_meta.get("config", {})
            .get("lifecycle", "keep_alive")
            or "keep_alive"
        )

        try:

            holder = self.mcp_client_cm.get(mcp_id)

            if not holder:
                logger.warning("[cache_first] No holder found in mcp_client_cm")
                return None

            if (
                holder.lifecycle != "keep_alive"
                or holder.lifecycle != lifecycle
            ):
                logger.info(f"[cache_first] Stop outdated MCP: {mcp_meta.get("mcp_name")}")
                
                await holder.stop()

                self.mcp_client_cm.pop(
                    mcp_id,
                    None,
                )

                return None

            logger.info(
                f"[cache_first] Reusing MCP "
                f"'{holder.mcp_name}' "
                f"(ID: {holder.mcp_id}, "
                f"lifecycle: {holder.lifecycle})"
            )

            return await holder.get_tools()

        except Exception as e:
            logger.error(
                f"[cache_first] Error while "
                f"reusing MCP tools: {e}"
            )
            return None

    async def load_all_mcp_tools(
        self,
        client_id: str,
    ) -> list[BaseTool]:
        logger.trace(f'[mcp_tool.py] [MCPToolManager] [load_all_mcp_tools] Enter')

        mcp_meta_list = await self.get_mcp_meta(
            client_id
        )

        all_tools: list[BaseTool] = []

        for mcp_meta in mcp_meta_list:

            cached_tools = await self.cache_first(
                mcp_meta
            )

            if cached_tools is not None:
                all_tools.extend(cached_tools)
                continue

            tools = await self.get_mcp_tools(
                mcp_meta
            )

            all_tools.extend(tools)

        return all_tools

    async def cleanup_all(self):

        holders = list(
            self.mcp_client_cm.values()
        )

        self.mcp_client_cm.clear()

        for holder in holders:
            try:
                await holder.stop()

            except Exception as e:
                logger.error(
                    f"[cleanup_all] Error while "
                    f"cleaning MCP '{holder.mcp_name}' "
                    f"(ID: {holder.mcp_id}): {e}"
                )


mcp_mgr = MCPToolManager()


@auto_init.auto_stop
async def clear_docker_container():
    await mcp_mgr.cleanup_all()