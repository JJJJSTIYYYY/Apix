import asyncio
from typing import Annotated

from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from apix_agent.apix_event_pipe.stream_writer import ApixStreamWriter, StreamEvent


@tool
async def run_workspace_command(
    command: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Execute a shell command inside Docker sandbox (/workspace).
    The sandbox must be configured before use this tool.

    Args: 
        command (str): The shell command to execute. 
        
    Returns: 
        str: The command output, or an error message if execution fails. 

    Note:
        Output will be truncated if exceeds 4000 characters.

    ## When to Use This Tool
    Use this tool in these scenarios:
    1. When you need to run programs, scripts, or development tools inside the workspace.
    2. When you need to execute CLI utilities (e.g., build tools, package managers, linters).
    3. When you need to inspect the workspace environment (e.g., list files, check system information).
    4. When a task requires executing commands that cannot be completed by other available tools.

    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. The task involves reading, creating, modifying, or deleting files (dedicated file tools should be used instead).
    2. The command is unrelated to the workspace task.
    3. The task can be completed directly through reasoning without executing a command.

    ## Important Guidelines
    - Ensure the command operates only within the `/workspace` directory.
    - Prefer safe and deterministic commands.
    - Avoid destructive commands unless explicitly required by the task.
    - Carefully check command syntax before execution.
    """
    client_id = state.get("client_id")
    target_platform = state.get("platform")

    event_writer = ApixStreamWriter()
    event_writer.send_event(
        event=StreamEvent.TOOL_EXEC_START, 
        target_id=client_id, 
        target_platform=target_platform,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "run_workspace_command",
            "tool_call_id": tool_call_id,
            "content": command,
            "chunk_position": "start",
            "status": "success",
        }
    )

    container_id = state.get("sandbox")

    if not container_id:
        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_workspace_command",
                "tool_call_id": tool_call_id,
                "content": "Error: Sandbox not configured.",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please call configure_sandbox first.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    if not command.strip():
        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_workspace_command",
                "tool_call_id": tool_call_id,
                "content": "Error: command is empty.",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage("Error: command cannot be empty.", tool_call_id=tool_call_id)
            ]
        })

    try:
        # Execute inside container
        cmd = [
            "docker", "exec",
            container_id,
            "bash", "-lc", command
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(), 
            timeout=600.0
        )

        output = stdout.decode() + stderr.decode()

        MAX_OUTPUT = 4000
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT//2] + "\n\n...[output truncated]...\n\n" + output[-MAX_OUTPUT//2:]

        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_workspace_command",
                "tool_call_id": tool_call_id,
                "content": f"{len(output.strip())} characters output." if output.strip() else "Command executed successfully (no output).",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    output.strip() or "Command executed successfully (no output).",
                    tool_call_id=tool_call_id
                )
            ]
        })
    
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()

        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_workspace_command",
                "tool_call_id": tool_call_id,
                "content": "Error: Command execution timed out after 600 seconds.",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Command execution timed out after 600 seconds.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    except Exception as e:

        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "run_workspace_command",
                "tool_call_id": tool_call_id,
                "content": f"Error: {str(e)}",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    f"Error: {str(e)}",
                    tool_call_id=tool_call_id
                )
            ]
        })
    