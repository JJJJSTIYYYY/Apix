import asyncio
import subprocess
import uuid
import os
import time
from typing import Dict, Any, Callable, Awaitable

import global_config


async def python_code_runner(
    task_id: str,
    payload: Dict[str, Any],
    progress_cb: Callable[[int, str], Awaitable[None]],
) -> Dict[str, Any]:
    """
    Execute Python code submitted by AI asynchronously.

    This function is executed inside the tools service.
    The execution progress and final result will be pushed
    to the memory server via callbacks.

    Args:
        task_id:
            Unique task id assigned by the tools service.

        payload:
            {
                "code": "<python source>",
                "run_args": [...],
                "timestamp": ...
            }

        progress_cb:
            Async callback to report execution progress (0-100, "stem message.").

    Returns:
        Dict[str, Any]:
            {
                "exit_code": int,
                "stdout": str,
                "stderr": str,
                "elapsed_sec": float
            }
    """
    start_time = time.time()

    pramas = payload.get("params", {})
    code: str = pramas.get("code", "")
    run_args = pramas.get("run_args") or []

    file_name = f"{uuid.uuid4()}.py"
    base_dir = global_config.BASE_DIR
    os.makedirs(base_dir, exist_ok=True)
    file_path = os.path.join(base_dir, file_name)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        await progress_cb(15, "Packaged code into script.")

        cmd = ["python", file_path, *run_args]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await progress_cb(40, "Created subprocess to run script.")

        stdout_bytes, stderr_bytes = await proc.communicate()

        await progress_cb(90, "Got script's output.")

        stdout = stdout_bytes.decode() if stdout_bytes else ""
        stderr = stderr_bytes.decode() if stderr_bytes else ""

        elapsed = time.time() - start_time

        await progress_cb(100, "Got standard output.")

        return {
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_sec": elapsed,
        }

    except Exception as e:
        await progress_cb(100, "Error Occured.")
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "elapsed_sec": time.time() - start_time,
        }

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
