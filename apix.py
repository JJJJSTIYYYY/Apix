import subprocess
import sys
import os
import signal
from pathlib import Path

# =========================
# Config
# =========================

ROOT = Path(__file__).resolve()

SERVICES = [
    "AGENT/agent_module",
    "MEMORY/memory_module",
    "FILE/file_service",
    "TOOLS/tools_module",
    "LOGIN_REGISTER/login_register_module",
    "TASK/task_flow_module",
]

LOG_DIR = ROOT / "logs"
PID_FILE = ROOT / ".apix_pids"


# =========================
# Utils
# =========================

def run(cmd, cwd=None):
    """Run shell command"""
    return subprocess.run(cmd, shell=True, cwd=cwd)


def start_service(path):
    """Start a single service"""
    name = path.replace("/", "_")
    log_file = LOG_DIR / f"{name}.log"

    print(f"[START] {path}")

    process = subprocess.Popen(
        "uv run main.py",
        cwd=ROOT / path,
        shell=True,
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT
    )

    return process.pid


def stop_process(pid):
    """Stop process by pid"""
    try:
        if os.name == "nt":
            subprocess.run(f"taskkill /PID {pid} /F", shell=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        print(f"[WARN] Failed to stop {pid}: {e}")


# =========================
# Commands
# =========================

def up():
    LOG_DIR.mkdir(exist_ok=True)

    pids = []

    print("==== Starting APIX Services ====")

    for svc in SERVICES:
        pid = start_service(svc)
        pids.append(pid)

    # save pids
    with open(PID_FILE, "w") as f:
        for pid in pids:
            f.write(str(pid) + "\n")

    print("\nAll services started ✅")


def down():
    if not PID_FILE.exists():
        print("No running services")
        return

    print("==== Stopping APIX Services ====")

    with open(PID_FILE) as f:
        for line in f:
            pid = int(line.strip())
            print(f"[STOP] {pid}")
            stop_process(pid)

    PID_FILE.unlink()
    print("All services stopped ✅")


def logs():
    print(f"Logs directory: {LOG_DIR}")


# =========================
# Entry
# =========================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apix.py [up|down|logs]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "up":
        up()
    elif cmd == "down":
        down()
    elif cmd == "logs":
        logs()
    else:
        print("Unknown command")