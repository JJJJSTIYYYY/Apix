import asyncio
from pathlib import Path
from typing import Annotated, List, Optional
from uuid import uuid4

from langchain.messages import ToolMessage
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.sandbox_manager.file_system_manager import file_system
from apix_agent.global_config import TOOLS_MAX_OUTPUT_LENGTH


@tool
async def run_python_code(
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
    5. When you want to sleep and wait for something to finish, using sleep().

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
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "run_python_code",
            "tool_call_id": tool_call_id,
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
    )

    run_args = run_args or []
    container_id = state.get("sandbox")
    config = state.get("config", {}) or {}
    sandbox_root = config.get("work_dir")

    if not container_id or not sandbox_root:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_python_code",
                "tool_call_id": tool_call_id,
                "content": "Error: Sandbox configure failed.",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        return Command(update={
            "messages": [
                ToolMessage("Error: Sandbox configure failed. Please info the user to configure it.", tool_call_id=tool_call_id)
            ]
        })

    if not code or not code.strip():
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_python_code",
                "tool_call_id": tool_call_id,
                "content": "Error: Python code cannot be empty.",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        return Command(update={
            "messages": [
                ToolMessage("Error: Python code cannot be empty.", tool_call_id=tool_call_id)
            ]
        })

    container_script_path = f"/workspace/.tmp_exec/{uuid4().hex}.py"

    try:
        host_script_path = file_system.get_file_path_in_host(
            file_path=container_script_path,
            container_workdir="/workspace",
            host_root=sandbox_root,
            must_exist=False,
        )

        if not isinstance(host_script_path, Path):
            event_writer.send_event(
                event=AgentStreamEvent.TOOL_EXEC_END, 
                target=target,
                data={
                    "event_name": "tool_exec_chunk_rtn",
                    "tool_name": "run_python_code",
                    "tool_call_id": tool_call_id,
                    "content": "Error: Failed to resolve host script path.",
                    "chunk_position": "end",
                    "status": "fail",
                }
            )
            return Command(update={
                "messages": [
                    ToolMessage("Error: Failed to resolve host script path.", tool_call_id=tool_call_id)
                ]
            })

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

        if len(output) > TOOLS_MAX_OUTPUT_LENGTH:
            output = output[:TOOLS_MAX_OUTPUT_LENGTH] + "\n...[output truncated]"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_python_code",
                "tool_call_id": tool_call_id,
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
        )

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

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_python_code",
                "tool_call_id": tool_call_id,
                "content": f"Error executing Python code: {str(e)}",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        return Command(update={
            "messages": [
                ToolMessage(f"Error executing Python code: {str(e)}", tool_call_id=tool_call_id)
            ]
        })

    finally:
        try:
            host_script_path = locals().get("host_script_path")
            if isinstance(host_script_path, Path) and host_script_path.exists():
                host_script_path.unlink()
        except Exception:
            pass