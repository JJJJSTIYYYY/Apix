import asyncio
import hashlib
import os
from pathlib import Path
import re
import shutil
from urllib.parse import unquote
from typing import Annotated, List, Optional
import shlex

import httpx
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from langgraph.config import get_stream_writer

from apix_agent import global_config
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.sandbox_manager.file_system_manager import file_system


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

@tool
async def get_file_by_id(
    file_ids: List[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Download user uploaded file(s) into sandbox workspace.

    Files will be stored in:
        /workspace/download_cache/

    This tool only downloads files.
    It does NOT validate file type or size.

    ## When to Use This Tool
    Use this tool in these scenarios:
    1. When the user explicitly asks to read, analyze, inspect, or process a previously uploaded file
    2. When the file user uploaded is necessary before continuing the task
    3. When the file must exist inside the sandbox workspace for execution
    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. You do not have a valid file ID provided by the system
    2. The task can be completed without accessing the file
    3. User has not uploaded any file or the file is irrelevant to the current task
    4. You want to download a file from the internet
    ## Important Guidelines
    - Only download files that are necessary for the current objective.
    - Avoid redundant downloads of the same file.
    """

    writer = get_stream_writer()

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "download_file",
            "content": str(file_ids),
            "chunk_position": "start",
            "status": "success",
        }
    })

    if not file_ids:
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
        return Command(update={
            "messages": [
                ToolMessage("Sandbox not configured.", tool_call_id=tool_call_id)
            ]
        })

    config = state.get("config", {})
    base_path = config.get("work_dir")

    if not base_path:
        return Command(update={
            "messages": [
                ToolMessage("work_dir not found.", tool_call_id=tool_call_id)
            ]
        })

    download_cache_dir = os.path.join(base_path, "download_cache")
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

                    return {
                        "status": "ok",
                        "path": "/workspace/"+target_path
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

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "download_file",
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        })

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

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "download_file",
            "content": f"{len(success_files)} success, {len(failed_files)} failed",
            "chunk_position": "end",
            "status": "success" if success_files else "fail",
        }
    })

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


@tool
async def _read_workspace_files(
    file_path: list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Read text files inside sandbox (/workspace) container.

    Args:
        file_path: A list of file paths to read.\
        Can be an absolute path inside the container or a relative path, which will be resolved from the container working directory (/workspace)

    Returns:
        list[dict]: [{ "file": path, "content": "..."}]

    Note: This tool can only read text file.
    """

    writer = get_stream_writer()

    writer({"tool_chunk_rtn": {
        "tool_call_id": tool_call_id,
        "tool_chunk_rtn": "read_files",
        "content": file_path,
        "chunk_position": "start",
        "status": "success",
    }})

    container_id = state.get("sandbox")

    if not container_id:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "read_files",
            "content": "Error: Sandbox not configured.",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(update={
            "messages": [
                ToolMessage("Error: Sandbox not configured. Please call configure_sandbox first.", tool_call_id=tool_call_id)
            ]
        })

    if not file_path:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "read_files",
            "content": "Error: No file path provided.",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(update={
            "messages": [
                ToolMessage("Error: No file_path provided.", tool_call_id=tool_call_id)
            ]
        })

    results = []

    try:
        success_count = 0
        for path in file_path:

            quoted_path = shlex.quote(path)

            cmd = [
                "docker", "exec",
                container_id,
                "bash", "-lc",
                f"cat -- {quoted_path}"
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                results.append({
                    "file": path,
                    "content": stderr.decode().strip()
                })
            else:
                success_count = success_count + 1
                results.append({
                    "file": path,
                    "content": stdout.decode()
                })

        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "read_files",
            "content": f"Read {success_count}/{len(file_path)} files successfully.",
            "chunk_position": "end",
            "status": "success",
        }})

        return Command(update={
            "messages": [
                ToolMessage(str(results), tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "read_files",
            "content": f"Error: {str(e)}",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(update={
            "messages": [
                ToolMessage(f"Error: {str(e)}", tool_call_id=tool_call_id)
            ]
        })
    

@tool
async def _write_workspace_file(
    file_name: str,
    content: str,
    over_write: bool,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Write text files inside sandbox (/workspace) container.

    Args:
        file_name: Name of file. Can be an absolute path inside the container or a relative path, which will be resolved from the container working directory (/workspace).
        content: File content.
        over_write: Over write exist file if true.

    Returns:
        list[dict]: [{ "file": path, "content": "..."}]

    Note: This tool can only write text file such as code file. If path is not exist, it will be created. Parent directory will also be created if not exist.
    """

    writer = get_stream_writer()
    writer({"tool_chunk_rtn": {
        "tool_call_id": tool_call_id,
        "tool_chunk_rtn": "write_file",
        "content": file_name,
        "chunk_position": "start",
        "status": "success",
    }})

    container_id = state.get("sandbox")

    if not container_id:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "write_file",
            "content": "Error: Sandbox not configured.",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(update={
            "messages": [
                ToolMessage("Error: Sandbox not configured. Please call configure_sandbox first.", tool_call_id=tool_call_id)
            ]
        })

    try:
        quoted_input_path = shlex.quote(file_name)

        resolve_cmd = [
            "docker", "exec",
            container_id,
            "bash", "-lc",
            f"realpath -m {quoted_input_path}"
        ]

        process = await asyncio.create_subprocess_exec(
            *resolve_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(stderr.decode().strip())

        resolved_path = stdout.decode().strip()

        if not (
            resolved_path == "/workspace"
            or resolved_path.startswith("/workspace/")
        ):
            writer({"tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "write_file",
                "content": f"Access denied: {resolved_path}",
                "chunk_position": "end",
                "status": "fail",
            }})

            return Command(update={
                "messages": [
                    ToolMessage(
                        f"Error: Path escapes /workspace: {resolved_path}",
                        tool_call_id=tool_call_id
                    )
                ]
            })

        quoted_resolved = shlex.quote(resolved_path)
        quoted_content = shlex.quote(content)

        if not over_write:
            check_cmd = [
                "docker", "exec",
                container_id,
                "bash", "-lc",
                f"test -f {quoted_resolved}"
            ]
            process = await asyncio.create_subprocess_exec(*check_cmd)
            await process.wait()

            if process.returncode == 0:
                writer({"tool_chunk_rtn": {
                    "tool_call_id": tool_call_id,
                    "tool_chunk_rtn": "write_file",
                    "content": f"File already exists.",
                    "chunk_position": "end",
                    "status": "fail",
                }})

                return Command(update={
                    "messages": [
                        ToolMessage(
                            f"Error: File already exists: {resolved_path}",
                            tool_call_id=tool_call_id
                        )
                    ]
                })

        write_cmd = [
            "docker", "exec",
            container_id,
            "bash", "-lc",
            f"mkdir -p $(dirname {quoted_resolved}) && echo {quoted_content} > {quoted_resolved}"
        ]

        process = await asyncio.create_subprocess_exec(*write_cmd)
        await process.wait()

        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "write_file",
            "content": f"Write success: {resolved_path}" if process.returncode == 0 else f"Failed to write file: {resolved_path}",
            "chunk_position": "end",
            "status": "success" if process.returncode == 0 else "fail",
        }})

        return Command(update={
            "messages": [
                ToolMessage(
                    f"Write file success: {resolved_path}",
                    tool_call_id=tool_call_id
                )
            ]
        })

    except Exception as e:
        writer({"tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "write_file",
            "content": f"Error: {str(e)}",
            "chunk_position": "end",
            "status": "fail",
        }})

        return Command(update={
            "messages": [
                ToolMessage(
                    f"Error: {str(e)}",
                    tool_call_id=tool_call_id
                )
            ]
        })
    

@tool
async def read_workspace_file(
    file_path: str,
    start_line: int = 0,
    end_line: int = 0,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Read a text file inside sandbox (/workspace).

    Args:
        file_path (str): File path inside container workspace
        start_line (int): 1-based inclusive start line. Use 0 to start from the beginning of the file.
        end_line (int): 1-based inclusive end line. Use 0 to read until the end of the file.

    Returns:
        File content with line numbers.
        Content format: [line_count_prefix] line_content
    """

    writer = get_stream_writer()
    if start_line in ["None", "0", None, "", 0]: start_line = None
    if end_line in ["None", "0", None, "", 0]: end_line = None

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "read_file",
            "content": file_path,
            "chunk_position": "start",
            "status": "success",
        }
    })

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured.",
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

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "read_file",
                "content": f"Read lines {s}-{e}",
                "chunk_position": "end",
                "status": "success",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(numbered, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "read_file",
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool
async def write_workspace_file(
    file_path: str,
    content: str,
    replace: int = False,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Create a new file or rewrite a exist file inside sandbox workspace.

    Args:
        file_path: File path inside container workspace
        content: File content
        replace: Replace entire file if already exist

    Returns:
        Full file content with line numbers
    """

    writer = get_stream_writer()

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "create_file",
            "content": file_path,
            "chunk_position": "start",
            "status": "success",
        }
    })

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured.",
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
            if host_path.exists() and not replace:
                raise Exception("File already exists")

            # Ensure parent directory exists
            host_path.parent.mkdir(parents=True, exist_ok=True)

            host_path.write_text(content, encoding="utf-8")

        numbered = "\n".join(
            f"[{i}] {line}"
            for i, line in enumerate(content.splitlines(keepends=False), start=1)
        )

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "create_file",
                "content": "File created",
                "chunk_position": "end",
                "status": "success",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(numbered, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "create_file",
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool
async def delete_workspace_file(
    file_path: str,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Delete a file or directory inside sandbox workspace.

    Args:
        file_path: File or directory path inside container workspace

    Returns:
        Success or error message
    """

    writer = get_stream_writer()

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "delete_file",
            "content": file_path,
            "chunk_position": "start",
            "status": "success",
        }
    })

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured.",
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

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "delete_file",
                "content": msg,
                "chunk_position": "end",
                "status": "success",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(msg, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "delete_file",
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool
async def move_workspace_file(
    source_path: str,
    target_path: str,
    delete_source: bool = True,
    state: Annotated[dict, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """
    Move or copy a file inside sandbox workspace.

    Args:
        source_path: Source file path inside container workspace
        target_path: Target file path inside container workspace
        delete_source: Whether to remove the source file after the operation.
          - True: move the file (delete the source after copying)
          - False: copy the file (keep the source file)

        Note: If the source file is undeletable, the operation will behave like a copy even.

    Returns:
        Success or error message
    """

    writer = get_stream_writer()

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "move_file",
            "content": f"{source_path} -> {target_path}",
            "chunk_position": "start",
            "status": "success",
        }
    })

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured.",
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

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "move_file",
                "content": msg,
                "chunk_position": "end",
                "status": "success",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(msg, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "move_file",
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })
    

@tool
async def list_workspace_files(
    path: Optional[str],
    recursively_scan: Optional[bool],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    List files and directories inside workspace.

    Args:
        path: Sub directory inside workspace (None means root)
        recursively_scan: Whether to recursively scan subdirectories (None means false)

    Returns:
        A tree-formatted directory listing of files and folders.
        The result is limited to a maximum of 500 items and a depth of 6 levels.
    """

    writer = get_stream_writer()
    if path == "None": path = None
    if recursively_scan == "None": recursively_scan = None

    writer({
        "tool_chunk_rtn": {
            "tool_call_id": tool_call_id,
            "tool_chunk_rtn": "list_files",
            "content": path or "/workspace",
            "chunk_position": "start",
            "status": "success",
        }
    })

    config = state.get("config", {})
    container_id = state.get("sandbox")
    sandbox_root = config.get("work_dir")

    if not container_id:
        return Command(update={
            "messages": [
                ToolMessage(
                    "Error: Sandbox not configured.",
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:

        if not path:
            target = Path(sandbox_root)
        else:
            target = file_system.get_file_path_in_host(
                file_path=path,
                container_workdir="/workspace",
                host_root=sandbox_root,
                must_exist=False
            )

        if not target.exists():
            raise Exception("Directory not found")

        if not target.is_dir():
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

        # -------------------------------------------------
        # Recursive tree scan (stable order for AI agents)
        # -------------------------------------------------
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
        scan_dir(target, 0)

        result = "\n".join(lines) if lines else "(empty directory)"

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "list_files",
                "content": f"{count} items",
                "chunk_position": "end",
                "status": "success",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(result, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:

        writer({
            "tool_chunk_rtn": {
                "tool_call_id": tool_call_id,
                "tool_chunk_rtn": "list_files",
                "content": str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        })

        return Command(update={
            "messages": [
                ToolMessage(str(e), tool_call_id=tool_call_id)
            ]
        })