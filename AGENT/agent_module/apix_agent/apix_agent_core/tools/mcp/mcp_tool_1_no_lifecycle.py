from contextlib import _AsyncGeneratorContextManager

import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient, SSEConnection, StdioConnection, StreamableHttpConnection, WebsocketConnection
from langchain_core.tools.base import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools

from apix_agent.commons.auto_init import auto_init
from apix_agent.commons.logger import logger
from apix_agent.global_config import MEMORY_SERVICE_BASE_URL
from apix_agent.commons.type_def import McpMetaSchema


class MCPToolManager:

    _instance = None

    def __new__(cls):
        # Ensure singleton instance
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.mcp_client_cm: list[dict[str, _AsyncGeneratorContextManager]] = []

    async def get_mcp_meta(self, client_id: str) -> list[McpMetaSchema]:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/mcp/get_enabled_mcp_servers",
                json={
                    "client_id": client_id,
                },
            )

        res = resp.json()
        if resp.status_code != 200 or not res.get('success'):
            logger.warning(f"[get_mcp_meta] Failed to update MCP server info to memory service: {resp.text}")
            return []
        
        return res.get('messages', [])
    

    async def create_mcp_client(self, mcp_meta: McpMetaSchema) -> MultiServerMCPClient | None:
        transport = mcp_meta['transport']
        mcp_name = mcp_meta['mcp_name']
        config = mcp_meta.get('config', {})

        try:
            if transport == "stdio":
                connection: StdioConnection = {
                    mcp_name: {
                        "transport": "stdio",
                        "command": config.get("command"),
                        "args": config.get("args", []),
                        "env": config.get("env", {}),
                        "cwd": config.get("cwd"),
                        "encoding": config.get("encoding", "utf-8"),
                        "session_kwargs": config.get("session_kwargs", {}),
                    }
                }
                mcp_client = MultiServerMCPClient(connection)
                logger.info(f"[create_mcp_client] Created MCP client for stdio transport: {mcp_name}")
                return mcp_client

            elif transport == "streamable_http":
                connection: StreamableHttpConnection = {
                    mcp_name: {
                        "transport": "streamable_http",
                        "url": config.get("url"),
                        "headers": config.get("headers", {}),
                        "timeout": 30,
                        "sse_read_timeout": 30,
                        "terminate_on_close": True,
                        "session_kwargs": config.get("session_kwargs", {}),
                    }
                }
                mcp_client = MultiServerMCPClient(connection)
                logger.info(f"[create_mcp_client] Created MCP client for {transport} transport: {mcp_name}")
                return mcp_client

            elif transport == "websocket":
                connection: WebsocketConnection = {
                    mcp_name: {
                        "transport": "websocket",
                        "url": config.get("url"),
                        "session_kwargs": config.get("session_kwargs", {}),
                    }
                }
                mcp_client = MultiServerMCPClient(connection)
                logger.info(f"[create_mcp_client] Created MCP client for {transport} transport: {mcp_name}")
                return mcp_client

            elif transport == "sse":
                connection: SSEConnection = {
                    mcp_name: {
                        "transport": "sse",
                        "url": config.get("url"),
                        "headers": config.get("headers", {}),
                        "timeout": 30,
                        "sse_read_timeout": 30,
                        "session_kwargs": config.get("session_kwargs", {}),
                    }
                }
                mcp_client = MultiServerMCPClient(connection)
                logger.info(f"[create_mcp_client] Created MCP client for {transport} transport: {mcp_name}")
                return mcp_client
            else:
                logger.warning(f"[create_mcp_client] Unknown transport type '{transport}' for MCP '{mcp_name}'. No client will be created.")
                return None
            
        except Exception as e:
            logger.error(f"[create_mcp_client] Error while creating MCP client: {e}")
            return None
    

    async def get_mcp_tools(self, mcp_meta: McpMetaSchema) -> list[BaseTool]:
        mcp_id = mcp_meta['mcp_id']
        mcp_name = mcp_meta['mcp_name']
        config = mcp_meta.get('config', {})
        lifecycle = config.get('lifecycle', 'keep_alive') or 'keep_alive'

        mcp_client = await self.create_mcp_client(mcp_meta)

        try:
            tools = []
            if lifecycle == "keep_alive":
                cm = mcp_client.session(mcp_name)
                session = await cm.__aenter__()

                self.mcp_client_cm.append({
                    "mcp_id": mcp_id,
                    "mcp_name": mcp_name,
                    "context_manager": cm,
                    "session": session,
                    "lifecycle": lifecycle,
                })

                tools = await load_mcp_tools(session)
                logger.info(f"[get_mcp_tools] MCP tools from stdio transport: {tools}")

            elif lifecycle == "agent_loop":
                cm = mcp_client.session(mcp_name)
                session = await cm.__aenter__()

                self.mcp_client_cm.append({
                    "mcp_id": mcp_id,
                    "mcp_name": mcp_name,
                    "context_manager": cm,
                    "session": session,
                    "lifecycle": lifecycle,
                })

                tools = await load_mcp_tools(session)
                logger.info(f"[get_mcp_tools] MCP tools from stdio transport: {tools}")

            elif lifecycle == "llm_invoke":
                tools = await mcp_client.get_tools()

            else:
                logger.warning(f"[get_mcp_tools] Unknown lifecycle '{lifecycle}' for MCP '{mcp_name}'. No tools will be loaded.")

            return tools

        except Exception as e:
            logger.error(f"[get_mcp_tools] Error while getting MCP tools: {e}")
            return []
        

    async def cache_first(self, mcp_meta: McpMetaSchema) -> list[BaseTool] | None:
        mcp_id = mcp_meta['mcp_id']
        lifecycle = mcp_meta.get('config', {}).get('lifecycle', 'keep_alive') or 'keep_alive'
        try:
            for item in self.mcp_client_cm:
                if item['mcp_id'] == mcp_id:
                    # lifecycle check
                    if item['lifecycle'] != 'keep_alive' or item["lifecycle"] != lifecycle:
                        await item['context_manager'].__aexit__(None, None, None)
                        self.mcp_client_cm.remove(item)
                        return None
                    logger.info(f"[cache_first] Found cached MCP client for MCP '{mcp_meta['mcp_name']}' (ID: {mcp_id}, lifecycle: {item['lifecycle']}). Reusing it.")
                    return await load_mcp_tools(item['session'])
        except Exception as e:
            logger.error(f"[cache_first] Error while caching MCP tools: {e}")
            return None
        return None


    async def load_all_mcp_tools(self, client_id: str) -> list[BaseTool]:
        mcp_meta_list = await self.get_mcp_meta(client_id)
        all_tools = []
        for mcp_meta in mcp_meta_list:
            cached_tools = await self.cache_first(mcp_meta)
            if cached_tools is not None:
                all_tools.extend(cached_tools)
                continue
            tools = await self.get_mcp_tools(mcp_meta)
            all_tools.extend(tools)
        return all_tools
    
    async def cleanup_all(self):
        for item in self.mcp_client_cm:
            try:
                await item['context_manager'].__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"[cleanup_all] Error while cleaning up MCP client for MCP '{item['mcp_name']}' (ID: {item['mcp_id']}): {e}")
        self.mcp_client_cm.clear()
    


mcp_mgr = MCPToolManager()

@auto_init.auto_stop
async def clear_docker_container():
    await mcp_mgr.cleanup_all()