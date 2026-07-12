from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apix_agent.apix_agent_core.agent_task.team_task_manager import team_task_manager
from apix_agent.apix_agent_core.agent_task.cron_task_manager import cron_task_manager

router = APIRouter(tags=["infomation"])


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
    task_list = await team_task_manager.query_all_tasks(expire=False)

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
    await team_task_manager.clear_finished_tasks()
    task_list = await team_task_manager.query_all_tasks(expire=False)

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

    res = await team_task_manager.stop_tasks(history_id=history_id, task_ids=[task_id], reason="user-initiated cancellation")

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "messages": res
        }
    )



@router.get("/api/v1/sync_cron/{task_id}/{repeat}/{time}")
async def sync_cron_tasks(task_id: str, repeat: str, time: str):
    """
    Lazy sync cron task after cron has any changed.
    """

    if not await cron_task_manager.lazy_sync_tasks(task_id, time, repeat):
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "messages": "Failed to sync cron tasks."
            }
        ) 
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "messages": "success"
        }
    )