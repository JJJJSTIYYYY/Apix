import asyncio
import hashlib
import os
from pathlib import Path
import re
import shutil
from urllib.parse import unquote
from typing import Annotated, List, Optional

import httpx
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent import global_config
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.sandbox_manager.file_system_manager import file_system
from apix_agent.apix_agent_core.tools.prompt import FETCH_FILE_PROMPT, READ_WORKSPACE_FILE_PROMPT, WRITE_WORKSPACE_FILE_PROMPT, DELETE_WORKSPACE_FILE_PROMPT, MOVE_WORKSPACE_FILE_PROMPT, LIST_WORKSPACE_FILES_PROMPT


# ------------------------------------------------------
# safer filename parsing
# ------------------------------------------------------

def extract_filename_from_header(content_disposition: str) -> Optional[str]:
    """Parse filename from Content-Disposition header safely."""
    if not content_disposition:
        return None

    # filename*=UTF-8''xxx
    match = re.search(r"filename\*\=UTF-8''([^;]+)", content_disposition)
    if match:
        return unquote(match.group(1))

    # filename="xxx"
    match = re.search(r'filename="([^"]+)"', content_disposition)
    if match:
        return match.group(1)

    return None


# ------------------------------------------------------
# atomic unique file creation (concurrency safe)
# ------------------------------------------------------

def open_unique_file_atomic(directory: str, filename: str):
    """
    Atomically create a unique file.
    Avoid race condition under concurrency.
    """
    base, ext = os.path.splitext(filename)
    counter = 0

    while True:
        if counter == 0:
            candidate = os.path.join(directory, filename)
        else:
            candidate = os.path.join(directory, f"{base}_({counter}){ext}")

        try:
            fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            return os.fdopen(fd, "wb"), candidate
        except FileExistsError:
            counter += 1


# ------------------------------------------------------
# main tool
# ------------------------------------------------------

@tool(description=FETCH_FILE_PROMPT)
async def fetch_files(
    file_ids: str | list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "fetch_files",
            "tool_call_id": tool_call_id,
            "content": str(file_ids),
            "chunk_position": "start",
            "status": "success",
        }
    )

    if not file_ids:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "fetch_files",
                "tool_call_id": tool_call_id,
                "content": "No file_id provided",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage("No file_ids provided.", tool_call_id=tool_call_id)
            ]
        })

    if isinstance(file_ids, str):
        file_ids = [file_ids]

    # ------------------------------------------------------
    # sandbox check
    # ------------------------------------------------------

    container_id = state.get("sandbox")
    if not container_id:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "fetch_files",
                "tool_call_id": tool_call_id,
                "content": "Sandbox not configured",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please info the user to configure it.", 
                    tool_call_id=tool_call_id
                )
            ]
        })

    config = state.get("config", {})
    base_path = config.get("work_dir")

    if not base_path:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "fetch_files",
                "tool_call_id": tool_call_id,
                "content": "work_dir not found",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage("work_dir not found.", tool_call_id=tool_call_id)
            ]
        })

    download_cache_dir = os.path.join(base_path, "user_uploaded")
    os.makedirs(download_cache_dir, exist_ok=True)

    base_url = global_config.FILE_SERVICE_URL.rstrip("/")
    download_url = f"{base_url}/file/file/download"

    semaphore = asyncio.Semaphore(5)  # limit concurrency

    # ------------------------------------------------------
    # download one file
    # ------------------------------------------------------

    async def download_one(file_id: str, client_id: str):

        async with semaphore:
            try:
                async with client.stream(
                    "GET",
                    download_url,
                    params={"file_id": file_id, "client_id": client_id},
                ) as response:

                    if response.status_code != 200:
                        return {
                            "status": "error",
                            "error": f"{file_id} http {response.status_code}"
                        }

                    filename = extract_filename_from_header(
                        response.headers.get("Content-Disposition", "")
                    )

                    if not filename:
                        return {
                            "status": "error",
                            "error": f"{file_id} missing filename"
                        }

                    filename = os.path.basename(filename)

                    file_obj, target_path = open_unique_file_atomic(
                        download_cache_dir,
                        filename
                    )

                    sha256 = hashlib.sha256()

                    try:
                        with file_obj as f:
                            async for chunk in response.aiter_bytes(1024 * 64):
                                f.write(chunk)
                                sha256.update(chunk)
                    except Exception:
                        if os.path.exists(target_path):
                            os.remove(target_path)
                        raise

                    # ---------------- hash verify ----------------

                    server_hash = response.headers.get("X-File-SHA256")

                    if server_hash:
                        local_hash = sha256.hexdigest()
                        if local_hash.lower() != server_hash.lower():
                            os.remove(target_path)
                            return {
                                "status": "error",
                                "error": f"{file_id} hash mismatch"
                            }

                    target_path = file_system.get_file_path_in_container(
                        file_path=target_path, container_workdir="/workspace", host_root=base_path, 
                    )
                    return {
                        "status": "ok",
                        "path": str(target_path)
                    }

            except Exception as e:
                return {
                    "status": "error",
                    "error": f"{file_id} {str(e)}"
                }

    # ------------------------------------------------------
    # shared http client (connection reuse)
    # ------------------------------------------------------

    try:
        async with httpx.AsyncClient(timeout=None) as client:

            results = await asyncio.gather(
                *(download_one(fid, state.get("client_id")) for fid in file_ids),
                return_exceptions=False
            )

    except Exception as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "fetch_files",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })

    # ------------------------------------------------------
    # result classification
    # ------------------------------------------------------

    success_files = [
        r["path"] for r in results
        if r.get("status") == "ok"
    ]

    failed_files = [
        r["error"] for r in results
        if r.get("status") == "error"
    ]

    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_END, 
        target=target, 
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "fetch_files",
            "tool_call_id": tool_call_id,
            "content": f"{len(success_files)} success, {len(failed_files)} failed",
            "chunk_position": "end",
            "status": "success" if success_files else "fail",
        }
    )

    message_text = (
        f"Downloaded {len(success_files)} file(s).\n"
        + ("\n".join(success_files) if success_files else "")
    )

    if failed_files:
        message_text += "\n\nFailed:\n" + "\n".join(failed_files)

    return Command(update={
        "messages": [
            ToolMessage(message_text, tool_call_id=tool_call_id)
        ]
    })

    

@tool(description=READ_WORKSPACE_FILE_PROMPT)
async def read_workspace_file(
    file_path: str,
    start_line: Optional[int] = 0,
    end_line: Optional[int] = 0,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target, 
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "read_workspace_file",
            "tool_call_id": tool_call_id,
            "content": file_path,
            "chunk_position": "start",
            "status": "success",
        }
    )

    if start_line in ["None", "0", None, "", 0]: start_line = None
    if end_line in ["None", "0", None, "", 0]: end_line = None

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_workspace_file",
                "tool_call_id": tool_call_id,
                "content": "Sandbox not configured",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please info the user to configure it",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:

        host_path = file_system.get_file_path_in_host(
            file_path=file_path,
            container_workdir="/workspace",
            host_root=sandbox_root
        )

        async with file_system.file_lock(host_path, state.get("agent_name", "Unnamed agent"), "read"):
            if host_path.stat().st_size > 5 * 1024 * 1024:
                raise Exception("File too large (>5MB)")

            lines = host_path.read_text(encoding="utf-8").splitlines(keepends=False)

        total = len(lines)

        s = 1 if not start_line else max(1, start_line)
        e = total if not end_line else min(end_line, total)

        selected = lines[s-1:e]

        numbered = "\n".join(
            f"[{i}] {line}"
            for i, line in zip(range(s, e+1), selected)
        )

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_workspace_file",
                "tool_call_id": tool_call_id,
                "content": f"Read lines {s}-{e}",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(numbered, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "read_workspace_file",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool(description=WRITE_WORKSPACE_FILE_PROMPT)
async def write_workspace_file(
    file_path: str,
    content: str,
    exist_ok: Optional[bool] = False,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target, 
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "write_workspace_file",
            "tool_call_id": tool_call_id,
            "content": file_path,
            "chunk_position": "start",
            "status": "success",
        }
    )

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_workspace_file",
                "tool_call_id": tool_call_id,
                "content": "Sandbox not configured",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please info the user to configure it.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:

        host_path = file_system.get_file_path_in_host(
            file_path=file_path,
            container_workdir="/workspace",
            host_root=sandbox_root,
            must_exist=False
        )
        
        async with file_system.file_lock(host_path, state.get("agent_name", "Unnamed agent"), "create"):
            # Ensure parent directory exists
            host_path.parent.mkdir(parents=True, exist_ok=True)

            if host_path.exists():
                if exist_ok:
                    # overwrite file
                    host_path.write_text(content, encoding="utf-8")
                    action = "overwritten"
                else:
                    raise FileExistsError(f"File already exists: {file_path}")
            else:
                # create new file
                host_path.write_text(content, encoding="utf-8")
                action = "created"

        # return one-line log instead of full content
        log_line = f"File {action}: {file_path}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_workspace_file",
                "tool_call_id": tool_call_id,
                "content": log_line,
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(log_line, tool_call_id=tool_call_id)
            ]
        })
    
    except FileExistsError as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_workspace_file",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(f"File already exists: {file_path}", tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "write_workspace_file",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool(description=DELETE_WORKSPACE_FILE_PROMPT)
async def delete_workspace_file(
    file_path: str,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target, 
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "delete_workspace_file",
            "tool_call_id": tool_call_id,
            "content": file_path,
            "chunk_position": "start",
            "status": "success",
        }
    )

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "delete_workspace_file",
                "tool_call_id": tool_call_id,
                "content": "Sandbox not configured",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please info the user to configure it",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:

        host_path = file_system.get_file_path_in_host(
            file_path=file_path,
            container_workdir="/workspace",
            host_root=sandbox_root,
            must_exist=True
        )

        if file_system.is_undeletable(host_path, sandbox_root, is_host_path=True):
            raise Exception(f"Refusing to delete {file_path}, it can not be deleted.")

        async with file_system.file_lock(host_path, state.get("agent_name", "Unnamed agent"), "delete"):
            if host_path.is_file():
                host_path.unlink()  # delete file
                msg = "File deleted"

            elif host_path.is_dir():
                shutil.rmtree(host_path)  # delete directory recursively
                msg = "Directory deleted"

            else:
                raise Exception("Target path is neither file nor directory")

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "delete_workspace_file",
                "tool_call_id": tool_call_id,
                "content": msg,
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(msg, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "delete_workspace_file",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool(description=MOVE_WORKSPACE_FILE_PROMPT)
async def move_workspace_file(
    source_path: str,
    target_path: str,
    delete_source: Optional[bool] = True,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target, 
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "move_workspace_file",
            "tool_call_id": tool_call_id,
            "content": f"{source_path} -> {target_path}",
            "chunk_position": "start",
            "status": "success",
        }
    )

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "move_workspace_file",
                "tool_call_id": tool_call_id,
                "content": "Sandbox not configured",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please info the user to configure it",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:
        source_host_path = file_system.get_file_path_in_host(
            file_path=source_path,
            container_workdir="/workspace",
            host_root=sandbox_root,
            must_exist=True
        )

        target_host_path = file_system.get_file_path_in_host(
            file_path=target_path,
            container_workdir="/workspace",
            host_root=sandbox_root,
            must_exist=False
        )

        async with file_system.multi_file_lock(
            [
                (source_host_path, "move" if delete_source else "read"),
                (target_host_path, "create"),
            ],
            state.get("agent_name", "Unnamed agent"),
        ):
            if target_host_path.exists():
                raise Exception("Target already exists")

            target_host_path.parent.mkdir(parents=True, exist_ok=True)

            if delete_source and not file_system.is_undeletable(source_host_path, sandbox_root, is_host_path=True):
                shutil.move(str(source_host_path), str(target_host_path))
                msg = f"File moved to {target_path}"
            else:
                shutil.copy2(str(source_host_path), str(target_host_path))
                msg = f"File copied to {target_path}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "move_workspace_file",
                "tool_call_id": tool_call_id,
                "content": msg,
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(msg, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "move_workspace_file",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool(description=LIST_WORKSPACE_FILES_PROMPT)
async def list_workspace_files(
    path: Optional[str] = '/workspace',
    recursively_scan: Optional[bool] = False,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target, 
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "list_workspace_files",
            "tool_call_id": tool_call_id,
            "content": path or "/workspace",
            "chunk_position": "start",
            "status": "success",
        }
    )

    if path == "None": path = None
    if recursively_scan == "None": recursively_scan = None

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target, 
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "list_workspace_files",
                "tool_call_id": tool_call_id,
                "content": "Sandbox not configured",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured. Please info the user to configure it",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:
        if not path:
            fs_target = Path(sandbox_root)
        else:
            fs_target = file_system.get_file_path_in_host(
                file_path=path,
                container_workdir="/workspace",
                host_root=sandbox_root,
                must_exist=False
            )

        if not fs_target.exists():
            raise Exception("Directory not found")

        if not fs_target.is_dir():
            raise Exception("Target is not a directory")

        MAX_FILES = 500
        MAX_DEPTH = 6

        # Directories ignored during recursive scanning
        IGNORE_DIRS = {
            ".git",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".venv",
            "venv"
        }

        lines = []
        count = 0

        # Recursive tree scan (stable order for AI agents)
        def scan_dir(current: Path, depth: int):
            nonlocal count

            with os.scandir(current) as entries:
                dirs = []
                files = []

                for entry in entries:

                    name = entry.name

                    # Ignore hidden folders and known large directories
                    if entry.is_dir():
                        if name.startswith(".") or name in IGNORE_DIRS:
                            continue
                        dirs.append(name)
                    else:
                        files.append(name)

                dirs.sort()
                files.sort()

                indent = "  " * depth

                # List directories first
                for d in dirs:
                    lines.append(f"{indent}{d}/")
                    count += 1

                    if count > MAX_FILES:
                        raise Exception("Too many files")

                    if recursively_scan and depth < MAX_DEPTH:
                        scan_dir(current / d, depth + 1)

                # Then list files
                for f in files:
                    lines.append(f"{indent}{f}")
                    count += 1

                    if count > MAX_FILES:
                        raise Exception("Too many files")

        # Start scan
        scan_dir(fs_target, 0)

        result = "\n".join(lines) if lines else "(empty directory)"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "list_workspace_files",
                "tool_call_id": tool_call_id,
                "content": f"{count} items",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(result, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "list_workspace_files",
                "tool_call_id": tool_call_id,
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })