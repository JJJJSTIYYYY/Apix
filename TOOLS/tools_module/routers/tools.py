from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx

import global_config as gc

router = APIRouter(tags=["tools"])


# ----------------------------------------------------------------------
# Tools registry
# Entry point for ToolMaker._fetch_tool_registry()
# tools -> memory -> tools registry passthrough
# ----------------------------------------------------------------------

@router.get("/tools/registry")
async def tools_registry():
    """
    Tools registry endpoint for AI service.

    This endpoint is the **entry point for ToolMaker** on the AI service side.
    It provides a unified tools registry by proxying the registry data
    from the Memory service.

    Design principles:
    - Tools service does NOT own tools metadata
    - Memory service is the single source of truth for tool definitions
    - Tools service acts as a thin, stateless proxy

    ------------------------------------------------------------------
    Request
    ------------------------------------------------------------------
    Method: POST
    Path: /tools/registry

    Request body:
        - Not required
        - Request object is reserved for future extensions
          (e.g. auth context, tenant routing)

    ------------------------------------------------------------------
    Response (this endpoint)
    ------------------------------------------------------------------
    Content-Type: application/json

    {
        "version": "1.0",
        "tools": [
            {
                "name": "search_api",
                "description": "Search API by keyword and return matched results.",
                "args_schema": {
                    "keyword": {
                        "type": "string",
                        "description": "Search keyword",
                        "required": true
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "description": "Maximum number of results"
                    }
                },
                "returns": {
                    "type": "object",
                    "description": "Search result payload"
                },
                "idempotent": true,
                "timeout": 30,
                "category": "read",
                "version_tag": "v1.2.0"
            }
        ],
        "timestamp": "2026-01-04T04:31:22.123456+00:00"
    }

    Notes:
    - `version` MUST match ToolMaker.SUPPORTED_REGISTRY_VERSION
    - `tools` is passed through without mutation
    - Additional metadata fields are preserved for future use

    ------------------------------------------------------------------
    Memory Service Dependency
    ------------------------------------------------------------------
    This endpoint directly proxies the following Memory service API:

        GET /memory/tools/registry

    Expected response format from Memory service:

    {
        "version": "1.0",
        "tools": [
            {
                "name": "string",
                "description": "string",
                "args_schema": {
                    "<param_name>": {
                        "type": "string | integer | number | boolean | array | object",
                        "description": "string",
                        "required": boolean (optional),
                        "default": any (optional)
                    }
                },
                "returns": {
                    "type": "string | object | array",
                    "description": "string"
                },
                "idempotent": boolean,
                "timeout": number,
                "category": "string",
                "version_tag": "string"
            }
        ]
    }

    Contract guarantees:
    - Memory service owns tool definitions and versioning
    - Tools service MUST NOT modify tool schema
    - Any breaking change must be done in Memory service only

    ------------------------------------------------------------------
    Error Handling
    ------------------------------------------------------------------
    - 500: Invalid registry format or internal error
    - 504: Memory service timeout
    - 200: Success (even if tools list is empty)

    ------------------------------------------------------------------
    Related Code Path
    ------------------------------------------------------------------
    ToolMaker.build_tools()
        -> ToolMaker._fetch_tool_registry()
            -> POST /tools/registry (this endpoint)
                -> GET /memory/tools/registry
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{gc.MEMORY_BASE_URL}/memory/tools/registry"
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch tools registry from memory service",
            )

        data = resp.json()

        if not isinstance(data, dict):
            raise HTTPException(status_code=500, detail="Invalid registry format")

        if data.get("version") != "1.0":
            raise HTTPException(
                status_code=500,
                detail=f"Unsupported registry version: {data.get('version')}",
            )

        tools = data.get("tools")
        if not isinstance(tools, list):
            raise HTTPException(status_code=500, detail="'tools' must be a list")

        return JSONResponse(
            content={
                "version": "1.0",
                "tools": tools,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status_code=200,
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Memory service timeout")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
