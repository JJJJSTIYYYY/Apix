import os
import shlex
import subprocess
from typing import Annotated

from langchain.messages import ToolMessage
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.config import get_stream_writer

from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox
from apix_agent.commons.logger import logger


@tool
async def configure_sandbox(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Configure a Docker-based sandbox for the current conversation.

    This will:
    - Create or reuse a sandbox container
    - Bind mount the configured work_dir into /workspace
    - Ensure container lifecycle is managed safely
    - After sandbox is configured, you can use command-line tools (apt, curl, wget, brew, etc.) 
      inside the container to install dependencies or cli-programs and customize your work environment
    """

    writer = get_stream_writer()
    writer({"tool_chunk_rtn": {
        "tool_call_id": tool_call_id,
        "tool_chunk_rtn": "configure_sandbox",
        "content": "Configuring sandbox...",
        "chunk_position": "start",
        "status": "success",
    }})

    # -------------------------
    # Extract state
    # -------------------------

    config = state.get("config", {})
    base_path = config.get("work_dir")
    client_id = state.get("client_id")
    conversation_id = state.get("history_id")

    # -------------------------
    # Validate inputs
    # -------------------------

    if not base_path:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "configure_sandbox",
            "content": "Error: No work dir specified.",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Error: No work_dir configured by user.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    if not client_id or not conversation_id:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "configure_sandbox",
            "content": "[SYSTEM LEVEL] Error: Missing essential configuration in generation loop.",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "[SYSTEM LEVEL] Error: Missing client_id or history_id in state. Please stop all of further execution.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    if not os.path.exists(base_path):
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "configure_sandbox",
            "content": "Missing work_dir. Please check if the path exists and is accessible.",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error: work_dir does not exist: {base_path}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    base_path = os.path.abspath(base_path)

    # -------------------------
    # Configure sandbox
    # -------------------------

    try:
        container_id = await agent_sandbox.configure_sandbox(
            client_id=client_id,
            conversation_id=conversation_id,
            work_dir=base_path,
        )

        if not container_id:
            raise RuntimeError("Failed to configure sandbox container.")
        
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "configure_sandbox",
            "content": 
                f"Sandbox configured successfully.\n"
                f"Mounted directory: {base_path}\n",
            "chunk_position": "end",
            "status": "success",
        }})

        return Command(
            update={
                "sandbox": container_id,
                "messages": [
                    ToolMessage(
                        f"Sandbox configured successfully.\n"
                        # f"Mounted directory: {base_path}\n"
                        f"Working directory inside container: /workspace",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except Exception as e:
        logger.exception(f'[configure_sandbox] Error occured: {str(e)}')
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "configure_sandbox",
            "content": f"Error: Failed to configure sandbox: {str(e)}",
            "chunk_position": "end",
            "status": "fail",
        }})
        
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Sandbox configuration failed: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )