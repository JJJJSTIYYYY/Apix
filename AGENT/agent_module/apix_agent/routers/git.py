import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.sandbox_manager.workspace_git_manager import workspace_git_manager


router = APIRouter(tags=["workspace_git"])


@router.post("/api/v1/workspace/check_git")
async def check_git_env(request: Request):
    """
    Check git environment and repository status.

    Request JSON:
    {
        "repo_path": str (optional)
    }

    Returns:
        {
            "success": bool,
            "messages": {
                "git_installed": bool,
                "git_version": str | None,
                "repo_exists": bool,
                "is_git_repo": bool
            }
        }
    """
    try:
        import asyncio

        body = await request.json()
        repo_path = body.get("repo_path")

        result = {
            "git_installed": False,
            "git_version": None,
            "repo_exists": False,
            "is_git_repo": False,
        }

        # Check if git is installed
        proc = await asyncio.create_subprocess_exec(
            "git",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode == 0:
            result["git_installed"] = True
            result["git_version"] = stdout.decode().strip()

        # Check repo status if path provided
        if repo_path:
            repo_path = os.path.abspath(repo_path)
            result["repo_exists"] = os.path.exists(repo_path)
            result["is_git_repo"] = os.path.exists(os.path.join(repo_path, ".git"))

        return JSONResponse(
            status_code=200,
            content={"success": True, "messages": result}
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )


@router.post("/api/v1/workspace/init")
async def init_workspace(request: Request):
    """
    Initialize workspace git repository.

    Request JSON:
    {
        "repo_path": str
    }

    Behavior:
        - Create directory if not exists
        - Initialize git repo
        - Configure user info
        - Enforce .gitignore
    """
    try:
        body = await request.json()
        repo_path = body.get("repo_path")

        # Initialize git repo
        await workspace_git_manager.init_git(repo_path, ensure_parent=True)

        # Ensure gitignore consistency
        await workspace_git_manager.ensure_gitignore(repo_path, rewrite=True)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages": "Workspace initialized"
            }
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )


@router.post("/api/v1/workspace/commit")
async def commit_workspace(request: Request):
    """
    Commit all changes in workspace.

    Request JSON:
    {
        "repo_path": str,
        "message": str (optional)
    }

    Behavior:
        - Auto add all files
        - Auto create branch if in detached HEAD
        - Return commit id
    """
    try:
        body = await request.json()
        repo_path = body.get("repo_path")
        message = body.get("message")

        commit_id = await workspace_git_manager.commit_all(repo_path, message)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages": {
                    "commit_id": commit_id
                }
            }
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )


@router.post("/api/v1/workspace/checkout")
async def checkout_workspace(request: Request):
    """
    Time travel to a specific commit.

    Request JSON:
    {
        "repo_path": str,
        "commit_id": str
    }

    Behavior:
        - Switch to target commit
        - Enter detached HEAD state
    """
    try:
        body = await request.json()
        repo_path = body.get("repo_path")
        commit_id = body.get("commit_id")

        await workspace_git_manager.checkout_commit(repo_path, commit_id)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages": f"Checked out {commit_id}"
            }
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )


@router.post("/api/v1/workspace/current")
async def get_current_state(request: Request):
    """
    Get current workspace state.

    Request JSON:
    {
        "repo_path": str
    }

    Returns:
        {
            "commit_id": str,
            "branch": str | None,
            "detached": bool
        }
    """
    try:
        body = await request.json()
        repo_path = body.get("repo_path")

        commit_id = await workspace_git_manager.get_current_commit(repo_path)
        branch = await workspace_git_manager.get_current_branch(repo_path)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages": {
                    "commit_id": commit_id,
                    "branch": branch,
                    "detached": branch is None
                }
            }
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )


@router.post("/api/v1/workspace/history")
async def get_history(request: Request):
    """
    Get commit history (git log).

    Request JSON:
    {
        "repo_path": str,
        "limit": int (optional)
    }

    Returns:
        List of commits:
            - commit_id
            - timestamp
            - message
    """
    try:
        body = await request.json()
        repo_path = body.get("repo_path")
        limit = body.get("limit", 50)

        history = await workspace_git_manager.get_commit_history(repo_path, limit)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages": history
            }
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )


@router.post("/api/v1/workspace/reflog")
async def get_reflog(request: Request):
    """
    Get reflog history.

    Request JSON:
    {
        "repo_path": str,
        "limit": int (optional)
    }

    Returns:
        List of reflog entries
    """
    try:
        body = await request.json()
        repo_path = body.get("repo_path")
        limit = body.get("limit", 50)

        logs = await workspace_git_manager.get_reflog(repo_path, limit)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages": logs
            }
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )


@router.post("/api/v1/workspace/graph")
async def get_graph(request: Request):
    """
    Get commit DAG for visualization.

    Request JSON:
    {
        "repo_path": str
    }

    Returns:
        Graph structure:
            commit_id -> { parents, children }
    """
    try:
        body = await request.json()
        repo_path = body.get("repo_path")

        graph = await workspace_git_manager.get_commit_graph(repo_path)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "messages": graph
            }
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "messages": str(e)}
        )