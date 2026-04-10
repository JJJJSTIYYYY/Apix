import subprocess
from typing import List
import os

import global_config


def python_script_runner(file_name: str, run_args: List[str]) -> str:
    """
    Run a Python script and return its output.
    The script will be executed using the current Python interpreter as:
        python <file_name> <run_args...>

    Args:
        file_name (str):
            Name of a `.py` script.
        run_args (List[str]):
            Optional command-line arguments passed as strings to the script.

    Returns:
        str:
            Combined stdout and stderr generated during execution.
            The format is:

                [stdout]
                <script stdout>

                [stderr]
                <script stderr>

            If both stdout and stderr are empty, returns:
                "No output"

            If the script file is missing or execution fails, the exception message
            is returned in the form:
                "python_runner Error: <message>"
    """
    try:
        file_name = os.path.join(global_config.BASE_DIR, file_name)
        # Build command: python script.py arg1 arg2 ...
        cmd = ["python", file_name, *run_args]

        # Execute synchronously
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Python 3.7+ auto-decodes
        )

        result = ""
        if proc.stdout:
            result += f"[stdout]\n{proc.stdout}"
        if proc.stderr:
            result += f"\n[stderr]\n{proc.stderr}"

        return result.strip() if result else "No output"

    except Exception as e:
        return f"python_runner Error: {str(e)}"
