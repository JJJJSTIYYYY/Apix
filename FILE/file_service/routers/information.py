import time
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.commons.logger import logger
from global_config import BASE_URL

router = APIRouter(tags=["information"])


@router.post("/file/info/get_models_list")
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
        config = body.get("config")
    except Exception as e:
        logger.error(f"[get_models_list]: Invalid request body: {e}")
        return JSONResponse(content={"messages": ['Error occured']}, status_code=400)

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
            raw_models_name_list.append(f'Error occured: {e}')
            logger.error(f"[get_models_list][ollama]: {e}")

    else:
        logger.error(f"[get_models_list]: Unsupported model_provider: {model_provider}")

    models_name_list = []
    for model_name in raw_models_name_list:
        if 'embed' in model_name:
            models_name_list.append(model_name)

    return JSONResponse(
        content={"messages": models_name_list},
        status_code=200
    )