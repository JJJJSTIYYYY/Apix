import asyncio
import json
import traceback
from typing import Callable, Dict
import httpx
import global_config as gcv
from typing import Protocol, Callable, Awaitable, Dict, Any

import global_config as gcv
from tools import tool

class ToolHandler(Protocol):
    async def __call__(
        self,
        task_id: str,
        payload: Dict[str, Any],
        progress_cb: Callable[[int], Awaitable[None]],
    ) -> Dict[str, Any]:
        ...


class TaskManager:
    """
    TaskManager is responsible for asynchronously consuming tool tasks,
    executing them with controlled concurrency, and reporting task status
    updates to the memory service via HTTP.

    Responsibilities:
    - Hold pending tasks until explicitly started
    - Execute registered tool handlers asynchronously
    - Control concurrency to avoid resource exhaustion
    - Report task status and result to memory service
    """

    def __init__(
        self,
        memory_base_url: str,
        worker_count: int = gcv.WORKER_COUNT,
    ):
        self.memory_base_url = memory_base_url.rstrip("/")
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_count = worker_count

        self.tool_handlers: Dict[str, ToolHandler] = {}
        self.http = httpx.AsyncClient(timeout=10)

        # Tasks waiting for manual start
        # task_id -> task data
        self.waiting_tasks: Dict[str, dict] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_tool(self, name: str, handler: ToolHandler):
        """
        Register a tool handler.
        """
        self.tool_handlers[name] = handler

    async def submit_task(
        self,
        task_id: str,
        task_hash: str,
        tool: str,
        payload: dict,
    ):
        """
        Submit a new task into waiting queue.
        Task will not be executed until task_start is called.
        """
        self.waiting_tasks[task_id] = {
            "task_id": task_id,
            "task_hash": task_hash,
            "tool": tool,
            "payload": payload,
        }

    async def kill_task(
        self,
        task_id: str,
    ):
        """
        Kill a task manually.

        Behavior:
        - If task is waiting: remove it from waiting queue.
        - If task is running: cancel the asyncio task.
        - If task does not exist or already finished: return False.

        Note:
        This is a cooperative cancellation.
        Actual termination depends on handler's asyncio behavior.
        """

        # Case 1: task is still waiting
        if task_id in self.waiting_tasks:
            self.waiting_tasks.pop(task_id, None)
            return True

        # Case 2: task is running
        running_task = self.running_tasks.get(task_id)
        if running_task:
            running_task.cancel()
            return True

        # Case 3: task not found
        return True

    async def task_start(self, task_id: str) -> bool:
        """
        Explicitly start a task.
        Move task from waiting queue into execution queue.
        """
        task = self.waiting_tasks.pop(task_id, None)
        if not task:
            return False

        task_hash = task["task_hash"]
        await self._update_task(task_hash, task_id, "running")
        await self.queue.put(task)
        return True

    async def start(self):
        """
        Start task consumers.
        """
        for i in range(self.worker_count):
            asyncio.create_task(self._worker_loop(i))

    async def shutdown(self):
        """
        Gracefully shutdown TaskManager.
        """
        await self.http.aclose()

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self, worker_id: int):
        """
        Continuously consume tasks from the execution queue.
        """
        while True:
            task_data = await self.queue.get()
            task_id = task_data["task_id"]

            task = asyncio.create_task(self._process_task(task_data))
            self.running_tasks[task_id] = task

            try:
                await task
            except asyncio.CancelledError:
                # Task was killed explicitly
                pass
            except Exception:
                traceback.print_exc()
            finally:
                self.running_tasks.pop(task_id, None)
                self.queue.task_done()

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def _process_task(self, data: dict):
        """
        Process a single tool task.
        """
        task_id = data["task_id"]
        task_hash = data["task_hash"]
        tool_name = data["tool"]
        payload = data.get("payload", {})

        handler = self.tool_handlers.get(tool_name)
        if not handler:
            await self._update_task(task_hash, task_id, "failed", {"error": "Unknown tool"})
            return

        async def progress_cb(p: int, info: str):
            await self._update_task(
                task_hash,
                task_id,
                "running",
                {"progress": p, "info": info},
            )

        try:
            result = await handler(task_id, payload, progress_cb)
            await self._update_task(task_hash, task_id, "done", result)
        except Exception as e:
            self.kill_task(task_id)
            await self._update_task(
                task_hash,
                task_id,
                "failed",
                {"error": str(e)},
            )

    # ------------------------------------------------------------------
    # HTTP → memory service
    # ------------------------------------------------------------------

    async def _update_task(
        self,
        task_hash: str,
        task_id: str,
        status: str,
        result: dict | None = None,
    ):
        payload = {
            "task_hash": task_hash,
            "task_id": task_id,
            "status": status,
        }

        if result is not None:
            payload["result"] = result

        try:
            resp = await self.http.post(
                f"{self.memory_base_url}/memory/task/update",
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()
            if not content.get("success"):
                raise RuntimeError("Task not found or has already expired.")
        except Exception as e:
            print(f"[TaskManager] update task failed: {e}")
            raise e



task_manager = TaskManager(gcv.MEMORY_BASE_URL, worker_count=4)

for key, value in tool.items():
    task_manager.register_tool(key, value)
