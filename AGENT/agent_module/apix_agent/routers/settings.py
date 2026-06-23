import os
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import asyncio
from urllib.parse import urlparse

from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.commons.logger import logger
from apix_agent.global_config import _ORIGINAL_PROXY_ENV

router = APIRouter(tags=["settings"])



async def _check_tcp_connectivity(proxy_url: str, timeout: float = 2.0):
    """
    Check whether proxy address (host:port) is reachable via TCP.

    Args:
        proxy_url (str): Proxy url, e.g. http://127.0.0.1:7890
        timeout (float): Connection timeout in seconds
    """
    parsed = urlparse(proxy_url)

    if not parsed.hostname or not parsed.port:
        raise ValueError(f"Invalid proxy format: {proxy_url}")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(parsed.hostname, parsed.port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        raise RuntimeError(
            f"Cannot connect to {parsed.hostname}:{parsed.port}"
        ) from e


@router.post("/api/v1/set_proxy")
async def set_proxy(request_data: Request):
    """
    Set httpx proxy.

    Args:
        request_data (Request): FastAPI request object containing client memory in JSON format.
            JSON structure:
            {
                "http_proxy": "...",
                "https_proxy": "...",
                "no_proxy": "...",
            }

    Returns:
        JSONResponse: {
            "messages": "...",
            "success": boolean,
        }
    """
    try:
        body = await request_data.json()
        logger.info(f"Set proxy: {body}")

        http_proxy = body.get("http_proxy", "")
        https_proxy = body.get("https_proxy", "")
        no_proxy = body.get("no_proxy", "")

        # ----------------
        # Handle HTTP proxy independently
        # ----------------
        if http_proxy:
            # Validate http proxy connectivity
            await _check_tcp_connectivity(http_proxy)
            os.environ["HTTP_PROXY"] = http_proxy
        else:
            # Restore original HTTP proxy
            original_http = _ORIGINAL_PROXY_ENV.get("HTTP_PROXY")
            logger.info(f"Set HTTP_PROXY: {original_http}")
            if original_http is None:
                os.environ.pop("HTTP_PROXY", None)
            else:
                os.environ["HTTP_PROXY"] = original_http

        # ----------------
        # Handle HTTPS proxy independently
        # ----------------
        if https_proxy:
            # Validate https proxy connectivity
            await _check_tcp_connectivity(https_proxy)
            os.environ["HTTPS_PROXY"] = https_proxy
        else:
            # Restore original HTTPS proxy
            original_https = _ORIGINAL_PROXY_ENV.get("HTTPS_PROXY")
            logger.info(f"Set HTTPS_PROXY: {original_http}")
            if original_https is None:
                os.environ.pop("HTTPS_PROXY", None)
            else:
                os.environ["HTTPS_PROXY"] = original_https

        # ----------------
        # Handle NO_PROXY (optional, independent)
        # ----------------
        if no_proxy is not None:
            os.environ["NO_PROXY"] = no_proxy
        else:
            # Restore original NO_PROXY if not provided
            original_no_proxy = _ORIGINAL_PROXY_ENV.get("NO_PROXY")
            logger.info(f"Set NO_PROXY: {original_http}")
            if original_no_proxy is None:
                os.environ.pop("NO_PROXY", None)
            else:
                os.environ["NO_PROXY"] = original_no_proxy

        return JSONResponse(
            content={
                "messages": "Proxy configuration updated",
                "success": True
            },
            status_code=200
        )

    except Exception as e:
        logger.error(f"Proxy address unreachable: {e}")
        return JSONResponse(
            content={
                "messages": f"Proxy address unreachable: {e}",
                "success": False
            },
            status_code=400
        )


async def _check_tcp_connectivity(proxy_url: str, timeout: float = 2.0):
    """
    Check whether proxy address (host:port) is reachable via TCP.

    Args:
        proxy_url (str): Proxy url, e.g. http://127.0.0.1:7890
        timeout (float): Connection timeout in seconds
    """
    parsed = urlparse(proxy_url)

    if not parsed.hostname or not parsed.port:
        raise ValueError(f"Invalid proxy format: {proxy_url}")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(parsed.hostname, parsed.port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        raise RuntimeError(
            f"Cannot connect to {parsed.hostname}:{parsed.port}"
        ) from e


@router.get("/api/v1/clear_vision_cache")
async def clear_vision_cache():
    """
    Clear vision cache.

    Returns:
        JSONResponse: {
            "messages": "...",
            "success": boolean,
        }
    """
    try:
        # 1. clear in-memory cache
        LlmNodeAdapter._vision_cache.clear()

        # 2. delete cache file if exists
        cache_file: Path = LlmNodeAdapter._cache_file_path

        if cache_file.exists():
            cache_file.unlink()  # delete file

        return JSONResponse({
            "messages": "Vision cache cleared successfully.",
            "success": True,
        })

    except Exception as e:
        return JSONResponse({
            "messages": f"Failed to clear vision cache: {str(e)}",
            "success": False,
        })