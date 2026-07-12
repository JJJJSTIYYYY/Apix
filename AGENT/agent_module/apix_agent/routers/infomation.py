import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from langchain_mcp_adapters.client import MultiServerMCPClient, SSEConnection, StdioConnection, StreamableHttpConnection, WebsocketConnection

from apix_agent.apix_agent_core.agent_task.team_task_manager import team_task_manager
from apix_agent.apix_platform.register import PLATFORM_REGISTRY
from apix_agent.commons.logger import logger
from apix_agent.global_config import BASE_URL, MEMORY_SERVICE_BASE_URL

router = APIRouter(tags=["infomation"])


@router.post("/api/v1/get_models_list")
async def get_models_list(request_data: Request):
    """
    Get available llm.

    Args:
        request_data (Request): FastAPI request object containing client memory in JSON format.
            JSON structure:
            {
                "model_provider": "...",
                "api_key": "...",
                "config": {}, // Optional
            }

    Returns:
        JSONResponse: llm name list.
    """
    raw_models_name_list = []

    try:
        body = await request_data.json()
        model_provider = body.get("model_provider")
        api_key = body.get("api_key")
        config = body.get("config", {}) or {}
    except Exception as e:
        logger.error(f"Invalid request body: {e}")
        return JSONResponse(content={"messages": ['Error occurred']}, status_code=400)

    # --------------------
    # Ollama (local and cloud)
    # --------------------
    if model_provider in ("ollama:local", "ollama"):
        try:
            response = httpx.get(f"{BASE_URL.get(model_provider)}/api/tags")
            response.raise_for_status()

            data = response.json()
            for model in data.get("models", []):
                # Ollama model name is stored in "name"
                raw_models_name_list.append(model.get("name"))

        except Exception as e:
            raw_models_name_list.append(f'Error occurred: {e}')
            logger.error(f"Failed to get ollama model: {e}")

    # --------------------
    # Google Gemini
    # --------------------
    elif model_provider == "google":
        # Google does NOT provide a public "list models" API
        # Fallback to known stable models
        raw_models_name_list = [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-pro"
        ]

    # --------------------
    # OpenAI-compatible providers
    # (Qwen / DeepSeek / XiaomiMIMO)
    # --------------------
    elif model_provider in ("openai", "qwen", "deepseek", "moonshot", "xiaomimimo"):
        try:

            response = httpx.get(
                f"{BASE_URL.get(model_provider)}/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()

            for model in response.json().get("data", []):
                raw_models_name_list.append(model.get("id"))

        except Exception as e:
            raw_models_name_list.append(f'Error occurred: {e}')
            logger.error(f"Failed to get {model_provider} model: {e}")

    elif model_provider == "custom":
        provider_id = None
        try:
            provider_id = config.get("custom_provider_id")
            response = await httpx.AsyncClient().post(
                f"{MEMORY_SERVICE_BASE_URL}/provider/get_llm_provider_by_id",
                json={
                    "provider_id": provider_id,
                },
            )
            response.raise_for_status()
            provider_metas = response.json().get("messages", []) or []
            if provider_metas:
                provider_meta = provider_metas[0]
            else:
                provider_meta = {}
            raw_models_name_list = provider_meta.get("model_list", []) or []

        except Exception as e:
            raw_models_name_list.append(f'Error occurred: {e}')
            logger.error(f"Failed to get {model_provider} model, provider_id={provider_id}: {e}")

    else:
        logger.error(f"Unsupported model provider: {model_provider}")

    models_name_list = sorted({
        model_name
        for model_name in raw_models_name_list
        if 'embed' not in model_name.lower() and 'tts' not in model_name.lower()
    })

    return JSONResponse(
        content={"messages": models_name_list},
        status_code=200
    )



@router.post("/api/v1/get_mcp_tools")
async def get_mcp_tools(request_data: Request):
    """
    Get MCP tools.

    Args:
        request_data (Request):
            JSON structure:
            {
                "client_id": str,
                "mcp_id": str,
                "mcp_meta": {
                    "mcp_name": str,
                    "transport": str,
                    "config": dict
                },
            }

    Returns:
        {
            "success": bool,
            "messages": list[str],
        }
    """
    body = await request_data.json()
    client_id = body.get("client_id")
    mcp_id = body.get("mcp_id")
    mcp_meta = body.get("mcp_meta", {})
    transport = mcp_meta.get("transport")
    config = mcp_meta.get("config", {})
    if transport not in ["stdio", "http", "websocket", "streamable_http", "sse"]:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "messages": f"Unsupported transport: {transport}"
            }
        )
    elif transport == 'http':
        transport = 'streamable_http'  # For backward compatibility, treat 'http' as 'streamable_http'

    try:
        tools = []
        if transport == "stdio":
            connection: StdioConnection = {
                mcp_meta.get("mcp_name"): {
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
            tools = await mcp_client.get_tools()
            logger.info(f"Get MCP tools from stdio transport: {tools}")

        elif transport == "streamable_http":
            connection: StreamableHttpConnection = {
                mcp_meta.get("mcp_name"): {
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
            tools = await mcp_client.get_tools()
            logger.info(f"Get MCP tools from {transport} transport: {tools}")

        elif transport == "websocket":
            connection: WebsocketConnection = {
                mcp_meta.get("mcp_name"): {
                    "transport": "websocket",
                    "url": config.get("url"),
                    "session_kwargs": config.get("session_kwargs", {}),
                }
            }
            mcp_client = MultiServerMCPClient(connection)
            tools = await mcp_client.get_tools()
            logger.info(f"Get MCP tools from {transport} transport: {tools}")

        elif transport == "sse":
            connection: SSEConnection = {
                mcp_meta.get("mcp_name"): {
                    "transport": "sse",
                    "url": config.get("url"),
                    "headers": config.get("headers", {}),
                    "timeout": 30,
                    "sse_read_timeout": 30,
                    "session_kwargs": config.get("session_kwargs", {}),
                }
            }
            mcp_client = MultiServerMCPClient(connection)
            tools = await mcp_client.get_tools()
            logger.info(f"Get MCP tools from {transport} transport: {tools}")


        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/mcp/update_mcp_server",
                json={
                    "mcp_id": mcp_id,
                    "client_id": client_id,
                    "tool_count": len(tools),
                },
            )

        if resp.status_code != 200 or not resp.json().get('success'):
            logger.warning(f"Failed to update MCP server info to memory service: {resp.text}")

    except Exception as e:
        logger.error(f"Error while getting MCP tools: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "messages": f"Error while getting MCP tools: {e}"
            }
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "messages": [tool.name for tool in tools]
        }
    )



@router.get("/api/v1/get_registered_platform")
async def get_registered_platform():
    """
    Get registered platform.

    Returns:
        {
            "success": bool,
            "messages": list[str],
        }
    """

