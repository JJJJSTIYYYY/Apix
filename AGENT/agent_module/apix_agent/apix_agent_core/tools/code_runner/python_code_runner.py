import asyncio
from pathlib import Path
import shlex
from typing import Annotated, List, Optional
from uuid import uuid4

import httpx
from langchain.messages import ToolMessage
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.config import get_stream_writer

from apix_agent import global_config
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.sandbox_manager.file_system_manager import file_system


@tool
async def _execute_python_code(
    code: str,
    run_args: Optional[List[str]] | None,
    describe: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """
    Submit Python source code for asynchronous execution in the tools service.

    This tool sends the provided Python code to a remote execution environment.
    The code is NOT executed locally.

    Execution is asynchronous:
    - If submission succeeds, a task will be created.
    - A unique task_id will be returned immediately.
    - The execution result will be delivered later through the task system.

    Use this tool when you need to:
    - Run non-trivial Python logic
    - Perform data processing or computation
    - Execute scripts that require isolated runtime

    Args:
        description (str): A short, clear description of the execution purpose.
        code (str): The complete Python source code to execute.
        args (List[str], optional): Command-line arguments passed to the script.

    Returns:
        str: The task_id of the submitted execution task.
    """
    logger.trace('[python_code_runner.py] [tool] [python_code_runner] Enter')
    try:
        client_id = state["client_id"]
        session_id = state.get("session_id")
        history_id = state["history_id"]
        config = state["config"]

        data = {
            "tool_name": "CodeRunner",
            "client_id": client_id,
            "history_id": history_id,
            "payload": {
                "describe": describe,
                "params": {
                    "code": code,
                    "run_args": run_args,
                },
                "config": config,
            },
        }

        logger.info(f"[python_code_runner] submit data: {data}")

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{global_config.TOOLS_SERVICE_URL}/execute/task",
                json=data,
            )

        resp_data = resp.json()
        return f"{resp_data}"

    except Exception as e:
        logger.exception("[python_code_runner] submit failed")
        return f"Failed to submit python execution task: {str(e)}"



@tool
async def execute_python_code(
    code: str,
    run_args: Optional[List[str]] = None,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Execute Python code immediately inside the sandbox environment.

    This tool runs Python code as a temporary script.
    The code is executed once and is NOT saved as a persistent workspace file.

    Args:
        code: Python code as a string.
        run_args: Optional command-line arguments passed to the script.

    Returns:
        Command output including stdout or error messages.

    ## When to Use This Tool
    Use this tool in these scenarios:
    1. When a task requires quick computation or data processing.
    2. When temporary Python code needs to be executed immediately.
    3. When performing one-off analysis, transformations, or calculations.
    4. When the code does not need to persist after execution.

    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. The Python program needs to be modified or reused later.
    2. The code should be saved as part of the workspace.
    3. The task requires iterative development or repeated execution of the same script.

    ## Important Guidelines
    - Code executed by this tool is ephemeral and will not be kept as a normal workspace source file.
    - If the program should persist in the workspace, write it to a file first.
    - Ensure required input files exist before execution.
    - Return outputs that help progress the task.
    """

    writer = get_stream_writer()
    state = state or {}
    run_args = run_args or []

    def finish_fail(message: str) -> Command:
        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "run_code",
                "content": message,
                "chunk_position": "end",
                "status": "fail",
            }
        })
        return Command(update={
            "messages": [
                ToolMessage(message, tool_call_id=tool_call_id)
            ]
        })

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "run_code",
            "content": (
                "Running Python code\n\n"
                "'''python\n"
                f"{code}\n"
                "'''\n"
                f"With args: {run_args}"
            ),
            "chunk_position": "start",
            "status": "success",
        }
    })

    container_id = state.get("sandbox")
    config = state.get("config", {}) or {}
    sandbox_root = config.get("work_dir")

    if not container_id or not sandbox_root:
        return finish_fail("Error: Sandbox configure failed.")

    if not code or not code.strip():
        return finish_fail("Error: Python code cannot be empty.")

    container_script_path = f"/workspace/.tmp_exec/{uuid4().hex}.py"

    try:
        host_script_path = file_system.get_file_path_in_host(
            file_path=container_script_path,
            container_workdir="/workspace",
            host_root=sandbox_root,
            must_exist=False,
        )

        if not isinstance(host_script_path, Path):
            return finish_fail("Error: Failed to resolve host script path.")

        host_script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(host_script_path, "w", encoding="utf-8", newline="") as f:
            f.write(code)

        run_cmd = [
            "docker",
            "exec",
            container_id,
            "python3",
            container_script_path,
            *run_args,
        ]

        process = await asyncio.create_subprocess_exec(
            *run_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        output_parts = []
        if stdout_text.strip():
            output_parts.append(stdout_text.rstrip())
        if stderr_text.strip():
            output_parts.append(stderr_text.rstrip())

        output = "\n".join(output_parts).strip()
        if not output:
            output = "Python code executed successfully (no output)."

        MAX_OUTPUT = 8000
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n...[output truncated]"

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "run_code",
                "content": (
                    "Result:\n"
                    "'''text\n"
                    "[STDOUT]\n"
                    f"{stdout_text}\n\n"
                    "[STDERR]\n"
                    f"{stderr_text}\n"
                    "'''"
                ),
                "chunk_position": "end",
                "status": "success" if process.returncode == 0 else "fail",
            }
        })

        if process.returncode != 0:
            return Command(update={
                "messages": [
                    ToolMessage(
                        f"Python exited with code {process.returncode}.\n{output}",
                        tool_call_id=tool_call_id,
                    )
                ]
            })

        return Command(update={
            "messages": [
                ToolMessage(output, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        return finish_fail(f"Error executing Python code: {str(e)}")

    finally:
        try:
            host_script_path = locals().get("host_script_path")
            if isinstance(host_script_path, Path) and host_script_path.exists():
                host_script_path.unlink()
        except Exception:
            pass