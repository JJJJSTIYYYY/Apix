import os
import hashlib
import asyncio
from typing import Dict, Optional
from uuid import uuid4

from apix_agent.global_config import SANDBOX_DOCKER_IMAGE_NAME


DOCKER_FILE = '''
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 基础工具
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Verify
RUN node -v && npm -v && python3 --version && pip3 --version

WORKDIR /workspace
'''


class AgentSandboxManager:
    """
    Global singleton Docker-based sandbox manager.

    - Each sandbox is identified by:
      hash(client_id + conversation_id + work_dir)

    - Concurrency safe
    - Async safe
    - Container lifecycle managed
    """

    def __init__(self):
        self._containers: Dict[str, str] = {}     # key -> container_id
        self._locks: Dict[str, asyncio.Lock] = {} # key -> lock
        self._global_lock = asyncio.Lock()

    # -------------------------
    # Public API
    # -------------------------

    async def configure_sandbox(
        self,
        *,
        client_id: str,
        conversation_id: str,
        work_dir: str,
    ) -> str:
        """
        Ensure sandbox container exists and return container_id.
        """

        if not os.path.exists(work_dir):
            return ""

        work_dir = os.path.abspath(work_dir)
        key = self._build_key(client_id, conversation_id, work_dir)

        async with await self._get_lock(key):

            # Container already exists
            if key in self._containers:
                container_id = self._containers[key]

                if await self._container_alive(container_id):
                    return container_id
                else:
                    # Clean stale container record
                    await self._safe_remove(container_id)
                    del self._containers[key]

            # Create new container
            container_id = await self._create_container(work_dir)

            self._containers[key] = container_id
            return container_id
        
    async def get_sandbox_container_id(
        self,
        *,
        client_id: str,
        conversation_id: str,
        work_dir: str,
    ) -> Optional[str]:
        """
        Get sandbox container id if exists, else None.
        """

        work_dir = os.path.abspath(work_dir)
        key = self._build_key(client_id, conversation_id, work_dir)

        async with await self._get_lock(key):
            container_id = self._containers.get(key)
            if container_id and await self._container_alive(container_id):
                return container_id
            else:
                # Clean stale container record
                if container_id:
                    await self._safe_remove(container_id)
                    del self._containers[key]
                return None

    async def destroy_sandbox(
        self,
        *,
        client_id: str,
        conversation_id: str,
        work_dir: str,
    ):
        """
        Stop and remove sandbox container.
        Files remain because of bind mount.
        """

        work_dir = os.path.abspath(work_dir)
        key = self._build_key(client_id, conversation_id, work_dir)

        async with await self._get_lock(key):

            container_id = self._containers.get(key)
            if not container_id:
                return

            await self._safe_remove(container_id)

            del self._containers[key]

    async def cleanup_all(self):
        """
        Stop all managed containers.
        """

        async with self._global_lock:
            keys = list(self._containers.keys())

        for key in keys:
            async with await self._get_lock(key):
                container_id = self._containers.get(key)
                if container_id:
                    await self._safe_remove(container_id)
                    del self._containers[key]

    async def docker_exec(self, container_id: str, cmd: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "sh", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return (out + err).decode()

    # -------------------------
    # Internal helpers
    # -------------------------

    def _build_key(self, client_id: str, conversation_id: str, work_dir: str) -> str:
        raw = f"{client_id}:{conversation_id}:{work_dir}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _get_lock(self, key: str) -> asyncio.Lock:
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def _create_container(self, work_dir: str) -> str:
        """
        Create Docker container using local Python image.

        - No repeated download
        - Bind mount work_dir to /workspace
        - Working dir: /workspace
        """

        image_name = SANDBOX_DOCKER_IMAGE_NAME

        # Check image exists locally
        await self._run_cmd(["docker", "image", "inspect", image_name])

        cmd = [
            "docker", "run",
            "-d",
            "--rm",                         # Auto remove when stopped
            "--network", "host",            # Share network with host
            "-v", f"{work_dir}:/workspace", # Bind mount
            "-w", "/workspace",             # Working directory
            "--name", f"agent_sandbox_{uuid4()}",
            image_name,
            "tail", "-f", "/dev/null"       # Keep container alive
        ]

        result = await self._run_cmd(cmd)
        return result.strip()

    async def _container_alive(self, container_id: str) -> bool:
        try:
            result = await self._run_cmd(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_id]
            )
            return result.strip() == "true"
        except Exception:
            return False

    async def _safe_remove(self, container_id: str):
        try:
            await self._run_cmd(["docker", "stop", container_id])
        except Exception:
            pass

    async def _run_cmd(self, cmd: list[str]) -> str:
        """
        Async subprocess runner.
        """

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(stderr.decode())

        return stdout.decode()
    


agent_sandbox = AgentSandboxManager()