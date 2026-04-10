import asyncio
from copy import deepcopy
from typing import Literal
from uuid import uuid4


TaskStatus = Literal["pending", "running", "finished"]


class TaskManager:
    """Manage auto test tasks with async-safe state transitions."""

    def __init__(self) -> None:
        self.pending_task: asyncio.Queue[str] = asyncio.Queue()
        self.running_task: asyncio.Queue[str] = asyncio.Queue()
        self.finished_task: asyncio.Queue[str] = asyncio.Queue()

        self._lock = asyncio.Lock()
        self._tasks: dict[str, dict] = {}
        self._client_tasks: dict[str, set[str]] = {}

    async def submit(
        self, client_id: str, content: list[dict], mock: str
    ) -> str:
        """
        Submit a batch of test tasks.

        Each content item becomes an independent pending task.
        """
        task_id = str(uuid4())

        async with self._lock:
            client_task_ids = self._client_tasks.setdefault(client_id, set())

            for item in content:
                case_id = str(uuid4())
                task = {
                    "id": case_id,
                    "task_id": task_id,
                    "client_id": client_id,
                    "mock": mock,
                    "name": item.get("name", ""),
                    "type": item.get("type", ""),
                    "address": item.get("address", ""),
                    "script": item.get("script", ""),
                    "description": item.get("description", ""),
                    "status": "pending",
                    "result": "",
                }
                self._tasks[case_id] = task
                client_task_ids.add(case_id)
                await self.pending_task.put(case_id)

        return task_id

    async def query(
        self, client_id: str, status: TaskStatus
    ) -> list[dict]:
        """Query tasks for one client by status."""
        async with self._lock:
            task_ids = self._client_tasks.get(client_id, set())
            return [
                deepcopy(self._tasks[task_id])
                for task_id in task_ids
                if self._tasks[task_id]["status"] == status
            ]

    async def get(self) -> list[dict]:
        """
        Fetch one pending task and all running task, then move it to the running state.

        This method blocks until a pending task is available.
        """
        case_id = await self.pending_task.get()

        async with self._lock:
            task = self._tasks.get(case_id)
            if task is None:
                raise KeyError(f"Task not found: {case_id}")
            if task["status"] != "pending":
                raise ValueError(
                    f"Only pending tasks can be fetched, got: {task['status']}"
                )

            task["status"] = "running"
            await self.running_task.put(case_id)
            return [
                deepcopy(current_task)
                for current_task in self._tasks.values()
                if current_task["status"] == "running"
            ]

    async def update(
        self,
        case_id: str,
        result: str,
        status: TaskStatus = "finished",
    ) -> dict:
        """
        Update a running task to finished and save its result.

        The only valid transition is running -> finished.
        """
        if status != "finished":
            raise ValueError("Only the 'finished' status is allowed in update().")

        async with self._lock:
            task = self._tasks.get(case_id)
            if task is None:
                raise KeyError(f"Task not found: {case_id}")
            if task["status"] != "running":
                raise ValueError(
                    "Only running tasks can be updated to finished."
                )

            task["status"] = "finished"
            task["result"] = result
            await self.finished_task.put(case_id)
            return deepcopy(task)


task_manager = TaskManager()
