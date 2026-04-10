import time
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apix_agent.apix_agent_core.agent_team_task.task_manager import task_manager
from apix_agent.commons.logger import logger
from apix_agent.global_config import BASE_URL

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

    # --------------------
    # OpenAI
    # --------------------
    elif model_provider == "openai":
        try:
            response = httpx.get(
                f"{BASE_URL.get(model_provider)}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()

            for model in response.json().get("data", []):
                # OpenAI model id is stored in "id"
                raw_models_name_list.append(model.get("id"))

        except Exception as e:
            raw_models_name_list.append(f'Error occured: {e}')
            logger.error(f"[get_models_list][openai]: {e}")

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
    # (Qwen / DeepSeek)
    # --------------------
    elif model_provider in ("qwen", "deepseek", "moonshot"):
        try:

            response = httpx.get(
                f"{BASE_URL.get(model_provider)}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()

            for model in response.json().get("data", []):
                raw_models_name_list.append(model.get("id"))

        except Exception as e:
            raw_models_name_list.append(f'Error occured: {e}')
            logger.error(f"[get_models_list] [{model_provider}]: {e}")

    else:
        logger.error(f"[get_models_list]: Unsupported model_provider: {model_provider}")

    models_name_list = []
    for model_name in raw_models_name_list:
        if 'embed' not in model_name:
            models_name_list.append(model_name)

    return JSONResponse(
        content={"messages": models_name_list},
        status_code=200
    )


@router.get("/api/v1/get_sub_agent_task_list")
async def get_sub_agent_task_list():
    """
    Get background task list.

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "history_id": str,
                    "task_id": str,
                    "agent_identity": str,
                    "final_goal": str,
                    "current_todo": str,
                    "duration": int,
                    "status": str,
                    "outputs": str,
                    "errors": str
                },
                ...
            ]
        }
    """
    task_list = await task_manager.query_all_tasks(expire=False)

    for task in task_list:
        current_todo_list = task.get("current_todo_list")
        todo_contents = []

        if isinstance(current_todo_list, list):
            for todo in current_todo_list:
                if isinstance(todo, dict) and todo.get("status") == "in_progress":
                    content = todo.get("content", "")
                    if content:
                        todo_contents.append(content)

        task["current_todo"] = "\n".join(todo_contents)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "messages": {
                "task_list": task_list,
                "total": len(task_list)
            }
        }
    )


@router.get("/api/v1/clear_finished_tasks")
async def clear_finished_tasks():
    """
    Clear finished background task.

    Returns:
        {
            "success": bool,
            "messages": [
                {
                    "history_id": str,
                    "task_id": str,
                    "agent_identity": str,
                    "final_goal": str,
                    "current_todo": str,
                    "duration": int,
                    "status": str,
                    "outputs": str,
                    "errors": str
                },
                ...
            ]
        }
    """
    await task_manager.clear_finished_tasks()
    task_list = await task_manager.query_all_tasks(expire=False)

    for task in task_list:
        current_todo_list = task.get("current_todo_list")
        todo_contents = []

        if isinstance(current_todo_list, list):
            for todo in current_todo_list:
                if isinstance(todo, dict) and todo.get("status") == "in_progress":
                    content = todo.get("content", "")
                    if content:
                        todo_contents.append(content)

        task["current_todo"] = "\n".join(todo_contents)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "messages": {
                "task_list": task_list,
                "total": len(task_list)
            }
        }
    )


@router.post("/api/v1/stop_task")
async def stop_task(request_data: Request):
    """
    Clear finished background task.

    Args:
        request_data (Request):
            JSON structure:
            {
                "task_id": str,
                "history_id": str,
            }

    Returns:
        {
            "success": bool,
            "messages": str,
        }
    """
    body = await request_data.json()
    task_id = body.get("task_id")
    history_id = body.get("history_id")
    logger.info(f"[stop_task] Stop task from: {history_id} - {task_id}")

    res = await task_manager.stop_tasks(history_id=history_id, task_ids=[task_id], reason="user-initiated cancellation")

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "messages": res
        }
    )