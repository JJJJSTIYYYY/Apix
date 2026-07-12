import asyncio
import calendar
import heapq
import io
import traceback
import inspect
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Tuple, TypedDict
from types import FunctionType
from contextlib import redirect_stdout, redirect_stderr

import httpx

from apix_agent.global_config import MEMORY_SERVICE_BASE_URL
from apix_agent.commons.type_def import ApixIdentity
from apix_agent.apix_event_pipe.common_event.agent_event_writer import (
    AgentCommonEvent,
    event_pipe,
)
from apix_agent.commons.auto_init import auto_init
from apix_agent.commons.logger import logger


class CronTask(TypedDict):
    id: str
    name: str
    target: ApixIdentity
    prompt: str
    execute: str
    exec_time: str | datetime
    repeat: Literal["once", "day", "week", "month", "year"]
    extra_config: dict


class CronTaskManager:
    """An asyncio-based cron-like scheduler that fires AgentCommonEvent.INFO
    events at the configured times.

    Internally maintains a min-heap of (exec_time, task_id, version) for
    efficient scheduling.  Lazy deletion via version numbers avoids expensive
    heap rebuilds.
    """

    def __init__(self) -> None:
        # id -> CronTask (exec_time always stored as datetime)
        self._tasks: Dict[str, CronTask] = {}
        # Monotonically increasing version per task id.
        # When a task is updated or cancelled, its version is bumped,
        # invalidating all previous heap entries.
        self._versions: Dict[str, int] = {}
        # Min-heap of (exec_time, task_id, version)
        self._heap: List[Tuple[datetime, str, int]] = []
        # Wakes the worker when a new task is added or a task is cancelled.
        self._wake_event: asyncio.Event = asyncio.Event()
        # Background worker task
        self._worker_task: Optional[asyncio.Task[None]] = None
        # Running flag for graceful shutdown
        self._running: bool = False

        self._need_sync: bool = False
        self._syncing_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_task_object(
        self,
        task_id: str,
        name: str,
        prompt: str,
        user_id: str,
        conversation_id: str,
        platform: str,
        exec_time: str | datetime,
        execute_code: str = None,
        repeat: Literal["once", "day", "week", "month", "year"] = "once",
    ) -> CronTask:
        """Create a new CronTask dictionary.  Does not add it to the manager."""
        return {
            "id": task_id,
            "name": name,
            "prompt": prompt,
            "target": {
                "id": user_id,
                "platform": platform,
                "conversation_id": conversation_id,
            },
            "exec_time": exec_time,
            "execute": execute_code,
            "repeat": repeat,
        }


    async def add_task(self, task: CronTask) -> None:
        """Register a new task or overwrite an existing one with the same id.

        After adding, the internal heap is updated and the worker is woken
        if the new task is the next to fire.
        """
        task_id = task["id"]

        # Parse exec_time to a concrete datetime if a string was provided.
        exec_time = self._parse_exec_time(task["exec_time"])

        if exec_time < datetime.now():
            if task["repeat"] == "once":
                await self._update_to_database(task["id"], {
                    "enabled": False
                })
                return
            # For repeating tasks, compute the next valid exec_time in the future.
            exec_time = await self.next_execute_time(task)

        execute = self._parse_execute(task["execute"])
        if execute is None:
            return

        # Store a copy so the caller's task is never modified.
        stored_task: CronTask = {
            **task,
            "exec_time": exec_time,
            "execute": execute
        }

        # Update version: if task already exists, bump version to invalidate
        # its current heap entry; otherwise start at 0.
        if task_id in self._tasks:
            self._versions[task_id] += 1
        else:
            self._versions[task_id] = 0

        self._tasks[task_id] = stored_task
        version = self._versions[task_id]
        heapq.heappush(self._heap, (exec_time, task_id, version))

        # Wake the worker so it can re-examine the heap (important when
        # the new exec_time is earlier than the current heap minimum).
        self._wake_event.set()


    def _cancel_task(self, task_id: str) -> None:
        """Deprecated
        Remove a task by id.  Uses lazy deletion: increments the version
        so that any pending heap entry becomes invalid."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._versions.pop(task_id, None)
            # Wake the worker so it can skip the now-invalid heap entry.
            self._wake_event.set()


    async def next_execute_time(self, task: str | CronTask, persist: bool = True) -> datetime:
        if isinstance(task, str):
            if task not in self._tasks:
                raise ValueError(f"The task with id {task} not found.")
            task = self._tasks[task]

        current = task.get("exec_time")
        current = self._parse_exec_time(current)
        
        next_exec_time = self._next_exec_time(current, task.get('repeat'))

        if next_exec_time == current or not persist:
            return next_exec_time
        
        await self._update_to_database(task.get("id"), {
            "exec_time": next_exec_time.isoformat()
        })

        return next_exec_time
    

    async def sync_tasks(self) -> bool:
        """Synchronize tasks from memory service.

        The database is treated as the source of truth. The local scheduler
        state is rebuilt from scratch.
        """
        logger.info('Start syncing cron tasks...')
        try:
            async with self._syncing_lock:
                tasks = await self._get_all_cron_task_from_database()

                # Clear current scheduler state.
                self._tasks.clear()
                self._versions.clear()
                self._heap.clear()

                # Rebuild scheduler.
                for task in tasks:
                    await self.add_task(task)

                # Wake the worker so it can rebuild its scheduling state.
                self._wake_event.set()
                self._need_sync = False

            logger.info('Sync cron tasks OK.')
            return True
            
        except Exception as e:
            logger.exception(f"Failed to sync cron tasks: {e}")
            return False


    async def lazy_sync_tasks(
        self,
        changed_task_id: str,
        changed_exec_time: str | datetime,
        changed_repeat: Literal["once", "day", "week", "month", "year"]
    ) -> None | bool:
        """Lazily synchronize tasks."""
        try:
            # No scheduled task, synchronize immediately.
            if not self._heap:
                logger.info('Lazy sync cron tasks immediately because of empty heap.')
                return await self.sync_tasks()

            heap_top_time, task_id, version = self._heap[0]
            if task_id == changed_task_id:
                logger.info('Lazy sync cron tasks immediately because of heap top task updated.')
                return await self.sync_tasks()

            logger.debug(f'Heap top time: {heap_top_time.isoformat()}.')
            temp_changed_exec_time = changed_exec_time
            changed_exec_time = self._next_exec_time(self._parse_exec_time(changed_exec_time), changed_repeat)

            if changed_exec_time <= heap_top_time:
                logger.info(f'Lazy sync cron tasks immediately because of earlier task updated: {temp_changed_exec_time}.')
                await self.sync_tasks()
            else:
                self._need_sync = True

            return True
        
        except Exception as e:
            logger.error(f"Failed to lazy sync tasks: {e}")
            return False


    async def start(self) -> None:
        """Launch the background worker.  Multiple calls are no-ops."""
        if self._running:
            return
        
        await self.sync_tasks()  # Ensure tasks are in sync with the memory service

        self._running = True
        self._wake_event.clear()
        self._worker_task = asyncio.create_task(
            self._worker(),
            name="CronTaskManager",
        )


    async def stop(self) -> None:
        """Gracefully stop the background worker.  After returning the
        manager can be started again with `start()`."""
        if not self._running:
            return

        self._running = False
        self._wake_event.set()

        if self._worker_task is not None:
            self._worker_task.cancel()

            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

            self._worker_task = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compile_execute(
        self,
        execute_code: str,
    ) -> Callable[[], Awaitable[str | None] | str | None]:
        """Compile execute code into a callable."""

        namespace: dict[str, object] = {
            "__builtins__": __builtins__,
        }

        try:
            exec(execute_code, namespace)
        except Exception as e:
            logger.exception(f"Can not compile source code: {e}")

        execute = namespace.get("apix_cron_main")

        if execute is None:
            raise ValueError(
                "execute_code must define a function named 'apix_cron_main'."
            )

        if not isinstance(execute, FunctionType):
            raise TypeError(
                "'apix_cron_main' must be a function."
            )

        signature = inspect.signature(execute)

        if signature.parameters:
            raise TypeError(
                "'apix_cron_main' must not accept any arguments."
            )

        return execute
    

    def _parse_exec_time(
        self,
        exec_time: str | datetime
    ) -> datetime:
        """Convert a string in ISO-8601 or 'YYYY-MM-DD HH:MM:SS' to datetime.
        A datetime object is returned unchanged."""
        if isinstance(exec_time, datetime):
            return exec_time
        # Try ISO format with 'T' separator
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(exec_time, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unrecognised exec_time format: {exec_time!r}")
    

    def _parse_execute(
        self,
        execute: str | None
    ) -> str | None:
        """Given a string that may be a file path (start with 'file://'),
        return the contents of that file; otherwise, return the original string.
        """
        if not execute.startswith("file://"):
            return execute

        file_path = execute[7:]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read execute file '{file_path}': {e}")
            return None

    
    def _next_exec_time(
        self,
        current: datetime,
        repeat: Literal["once", "day", "week", "month", "year"],
    ) -> datetime:
        """Compute the next valid execution time based on the repeat rule."""

        if repeat == "once":
            return current

        now = datetime.now()
        next_time = current

        while next_time <= now:
            if repeat == "day":
                next_time += timedelta(days=1)

            elif repeat == "week":
                next_time += timedelta(weeks=1)

            elif repeat == "month":
                year = next_time.year
                month = next_time.month + 1
                if month > 12:
                    year += 1
                    month = 1

                day = min(next_time.day, calendar.monthrange(year, month)[1])
                next_time = next_time.replace(
                    year=year,
                    month=month,
                    day=day,
                )

            elif repeat == "year":
                year = next_time.year + 1
                day = min(
                    next_time.day,
                    calendar.monthrange(year, next_time.month)[1],
                )
                next_time = next_time.replace(
                    year=year,
                    day=day,
                )

            else:
                raise ValueError(f"Unknown repeat value: {repeat!r}")

        return next_time
    

    async def _get_all_cron_task_from_database(self)-> list[CronTask]:
        """Get all enabled task from database."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{MEMORY_SERVICE_BASE_URL}/cron/get_all_enabled_cron_tasks",
                )

            response.raise_for_status()

            data = response.json()

            if not data.get("success", []):
                raise RuntimeError(
                    data.get("messages") or "Update cron task failed."
                )
            
            raw_crons = data.get("messages")
            crons: list[CronTask] = [
                {
                    "id": cron["task_id"],
                    "name": cron["name"],
                    "target": {
                        "id": cron["user_uid"], 
                        "platform": cron["platform"],
                        "conversation_id": cron["conversation_uid"],
                    },
                    "prompt": cron["prompt"],
                    "execute": cron["execute"],
                    "exec_time": cron["exec_time"],
                    "repeat": cron["repeat"],
                    "extra_config": cron.get("extra_config") or {},
                }
                for cron in raw_crons
            ]

            return crons

        except Exception:
            logger.exception("Failed to get cron tasks.",)
            raise
        
    
    async def _update_to_database(
        self,
        task_id: str,
        updates: dict,
    ) -> None:
        """Update cron task data to mysql."""
        # Idea: using background thread or task to update
        payload = {
            "task_id": task_id,
            **updates,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{MEMORY_SERVICE_BASE_URL}/cron/update_cron_task",
                    json=payload,
                )

            response.raise_for_status()

            data = response.json()

            if not data.get("success"):
                raise RuntimeError(
                    data.get("messages") or "Update cron task failed."
                )

        except Exception:
            logger.exception(
                "Failed to update cron task '%s'.",
                task_id,
            )
            raise


    async def _execute_task(self, task: CronTask, scheduled_time: datetime) -> None:
        """Run the optional execute hook, assemble the final prompt, and post
        the AgentCommonEvent.INFO event."""
        execute_result: str | None = None
        execute_code_output: Dict[str, str] = {"stdout": "", "stderr": ""}

        execute_code = task.get("execute")

        if execute_code:

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            execute = self._compile_execute(execute_code)

            with (
                redirect_stdout(stdout_buffer),
                redirect_stderr(stderr_buffer),
            ):
                result = execute()

                if inspect.isawaitable(result):
                    execute_result = await result
                else:
                    execute_result = result

            execute_code_output["stdout"] = stdout_buffer.getvalue() or ""
            execute_code_output["stderr"] = stderr_buffer.getvalue() or ""

        if execute_code_output["stdout"] or execute_code_output["stderr"]:
            exec_log = [
                f"[ TASK {task['id']} - {datetime.now().isoformat(sep=' ')} ]",
                f"[ EXECUTE CODE STDOUT ] {execute_code_output['stdout']}",
                f"[ EXECUTE CODE STDERR ] {execute_code_output['stderr']}"
            ]
            exec_log = "\n".join(exec_log) + '\n\n'
            await logger.write_log("cron_task_execute", f"{task['name']}_{task['id']}", exec_log)

        await event_pipe.post_event(
            event=AgentCommonEvent.INFO,
            target=task["target"],
            data={
                "event_name": "on_cron_task_triggered",
                "content": {
                    "task_id": task["id"],
                    "task_name": task["name"],
                    "repeat": task["repeat"],
                    "scheduled_time": scheduled_time.isoformat(),
                    "trigger_time": datetime.now().isoformat(),
                    "prompt": task["prompt"],
                    "execute_result": execute_result or "",
                    "execute_code_output": execute_code_output,
                    "extra_config": task["extra_config"]
                },
            },
        )


    async def _worker(self) -> None:
        """Main scheduling loop that runs as a background asyncio Task."""
        try:
            while self._running:
                # If nothing to schedule, sleep until woken.
                if not self._heap:
                    await self._wake_event.wait()
                    self._wake_event.clear()
                    continue

                exec_time, task_id, version = self._heap[0]
                now = datetime.now()

                if now < exec_time:
                    # Sleep until the next scheduled time, but allow early wake-up
                    # when a new task is added or a task is cancelled.
                    timeout = (exec_time - now).total_seconds()
                    try:
                        await asyncio.wait_for(self._wake_event.wait(), timeout=timeout)
                    except asyncio.TimeoutError:
                        # Time to fire the task – fall through.
                        pass
                    else:
                        # Woken early (e.g. new task added). Clear the event and
                        # re-evaluate the heap.
                        self._wake_event.clear()
                        continue

                if not self._heap:
                    continue

                # Pop the top entry and validate it.
                heapq.heappop(self._heap)
                task = self._tasks.get(task_id)
                current_version = self._versions.get(task_id, -1)
                if task is None or current_version != version:
                    # Stale heap entry – skip and loop.
                    continue

                # Execute the task (exceptions are caught so the worker never dies).
                try:
                    await self._execute_task(task, exec_time)
                except Exception:
                    traceback.print_exc()

                # Handle repeat or one-shot removal.
                if task["repeat"] == "once":
                    # Remove the task; old heap entries are already invalidated
                    # by the version check, so no extra cleanup is needed.
                    self._tasks.pop(task_id, None)
                    # Bump version so future stale entries are ignored.
                    self._versions.pop(task_id, None)
                    await self._update_to_database(task_id, {
                        "enabled": False
                    })
                else:
                    # Compute next execution time and re-insert into the heap.
                    next_time = await self.next_execute_time(task)
                    task["exec_time"] = next_time  # update in-place
                    new_version = self._versions[task_id] + 1
                    self._versions[task_id] = new_version
                    heapq.heappush(self._heap, (next_time, task_id, new_version))

                # Synchronize tasks if there are deferred updates.
                if self._need_sync:
                    self._need_sync = False
                    await self.sync_tasks()
                    continue

        except asyncio.CancelledError:
            raise



cron_task_manager = CronTaskManager()

auto_init.register(cron_task_manager)
