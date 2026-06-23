import asyncio
import time
from typing import Tuple
from uuid import uuid4

from apix_agent.commons.logger import logger
from apix_agent.commons.type_def import AgentConfigSchema, SubAgentState
from apix_agent.apix_event_pipe.common_event.agent_event_writer import AgentCommonEvent, event_pipe


class TeamTaskManager:

    _instance = None

    def __new__(cls):
        # Ensure singleton instance
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.TASK_RESULT_TTL = 3600
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.stop_request_queue: asyncio.Queue = asyncio.Queue()
        self.task_state_store: dict[Tuple[str, str], SubAgentState] = {}
        self.generation_tasks: dict[str, set[str]] = {} # To collect assigned task in one generation.
        self.task_generation: dict[str, str] = {} # To index a generation_id by task_id
        self.unreaded_tasks: set[str] = {}

        self._state_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit_task(self, initial_state: SubAgentState, config: AgentConfigSchema, agent_name: str, generation_id: str) -> str:
        task_id = str(uuid4())
        initial_state["task_id"] = task_id
        history_id = initial_state["history_id"]

        async with self._state_lock:
            self.task_state_store[((history_id, task_id))] = initial_state
            self.generation_tasks.setdefault(generation_id, set()).add(task_id)
            self.task_generation[task_id] = generation_id

        if self.task_queue is None:
            self.task_queue = asyncio.Queue()

        await self.task_queue.put((agent_name, initial_state, config))

        await event_pipe.post_event(
            event=AgentCommonEvent.INFO,
            target=initial_state.get("target"),
            data={
                "event_name": "on_team_task_task_submitted",
                "content": {
                    "agent_name": agent_name,
                    "initial_state": initial_state
                }
            }
        )
        return task_id


    async def query_tasks(self, history_id: str, task_ids: list[str], *, expire: bool = True) -> list:
        current_timestamp = int(time.time())

        async with self._state_lock:
            # states = [self.task_state_store.get(task_id) for task_id in task_ids if task_id.strip()]
            all_states = self.task_state_store.copy()

        states = []
        if not task_ids:
            states = [all_states.get(key) for key in all_states.keys() if key[0] == history_id]
        else:
            states = [all_states.get((history_id, task_id)) for task_id in task_ids if task_id.strip()]

        task_status = []
        expired_tasks = []

        for state in states:
            if not state:
                continue
            create_at = state.get("start_timestamp", current_timestamp)
            finish_at = state.get("finish_timestamp", current_timestamp)
            duration = (finish_at or current_timestamp) - create_at
            task_id = state.get("task_id")
            todos = state.get("todos")
            outputs = state.get("outputs")
            errors = state.get("errors")

            task_status.append({
                "task_id": task_id,
                "agent_identity": state["agent_name"],
                "final_goal": state.get("final_goal"),
                "current_todo_list": todos if todos else "No todo list generated yet.",
                "duration": f"{duration} seconds",
                "status": state.get("status"),
                "outputs": outputs if outputs else "No content generated yet.",
                "errors": errors if errors else "No error occurred."
            })

            status = state.get("status")
            if status in ["completed", "failed", "cancelled"]:
                finish_at = state.get("finish_timestamp", current_timestamp)
                if current_timestamp - finish_at > self.TASK_RESULT_TTL:
                    expired_tasks.append(task_id)

        if expired_tasks and expire:
            async with self._state_lock:
                for task_id in expired_tasks:
                    self.task_state_store.pop((history_id, task_id), None)

        return task_status


    async def query_all_tasks(self, *, expire: bool = False) -> list:
        current_timestamp = int(time.time())

        async with self._state_lock:
            states = self.task_state_store.copy()

        task_status = []
        expired_tasks = []

        for key, state in states.items():
            if not state:
                continue
            create_at = state.get("start_timestamp", current_timestamp)
            finish_at = state.get("finish_timestamp", current_timestamp)
            duration = (finish_at or current_timestamp) - create_at
            task_id = state.get("task_id")
            todos = state.get("todos")
            outputs = state.get("outputs")
            errors = state.get("errors")

            task_status.append({
                "history_id": key[0],
                "task_id": task_id,
                "agent_identity": state["agent_name"],
                "final_goal": state.get("final_goal"),
                "current_todo_list": todos if todos else "No todo list generated yet.",
                "duration": duration,
                "status": state.get("status"),
                "outputs": outputs if outputs else "No content generated yet.",
                "errors": errors if errors else "No error occurred."
            })

            status = state.get("status")
            if status in ["completed", "failed", "cancelled"]:
                finish_at = state.get("finish_timestamp", current_timestamp)
                if current_timestamp - finish_at > self.TASK_RESULT_TTL:
                    expired_tasks.append((key[0], task_id))

        if expired_tasks and expire:
            async with self._state_lock:
                for task in expired_tasks:
                    self.task_state_store.pop(task, None)

        return task_status
    

    async def clear_finished_tasks(self) -> int:
        """
        Clear all finished tasks from task_state_store.

        Finished status includes:
        - completed
        - failed
        - cancelled

        Returns:
            int: number of cleared tasks
        """
        finished_keys = []

        async with self._state_lock:
            for key, state in self.task_state_store.items():
                if not state:
                    continue

                status = state.get("status")
                if status in ["completed", "failed", "cancelled"]:
                    finished_keys.append(key)

            for key in finished_keys:
                self.task_state_store.pop(key, None)

        return len(finished_keys)
    

    async def stop_tasks(self, history_id, task_ids: list[str], *, reason: str = "") -> str:
        """
        Submit stop requests for the specified tasks.
        """

        if not task_ids:
            return "No task ids provided."
        if self.stop_request_queue is None:
            self.stop_request_queue = asyncio.Queue()

        stopped = []
        not_found = []
        async with self._state_lock:
            for task_id in task_ids:
                if not task_id or not task_id.strip():
                    continue
                state = self.task_state_store.get((history_id, task_id))
                if not state:
                    not_found.append(task_id)
                    continue

                state['status'] = "cancelled"
                state['errors'] = "Task canceled due to "+reason
                stopped.append(task_id)
        
                await event_pipe.post_event(
                    event=AgentCommonEvent.INFO,
                    target=state.get("target"),
                    data={
                        "event_name": "on_team_task_stop_submitted",
                        "content": {
                            "task_id": task_id
                        }
                    }
                )

        # Put stop requests outside lock to avoid blocking state operations
        for task_id in stopped:
            await self.stop_request_queue.put(task_id)
        if not stopped:
            return f"No valid tasks found. Not found: {not_found}"
        if not_found:
            return f"Stop request submitted for tasks: {stopped}. Not found: {not_found}"

        return f"Stop request submitted for tasks: {stopped}"


    async def update_task_state_store(
        self,
        history_id: str,
        task_id: str,
        **updates,
    ):
        return await self._update_task(
            history_id,
            task_id,
            **updates,
        )


    async def _update_task(
        self,
        history_id: str,
        task_id: str,
        **updates,
    ):
        async with self._state_lock:
            state = self.task_state_store.get((history_id, task_id))
            if not state:
                return None

            state.update(updates)

            return state.get("target")
        

    async def _update_unreaded_task(
        self,
        task_id: str,
        readed: bool
    ):
        async with self._state_lock:
            if readed:
                self.unreaded_tasks.discard(task_id)

            else:
                self.unreaded_tasks.add(task_id)


    async def mark_in_progress(
        self,
        history_id: str,
        task_id: str,
    ):
        target = await self._update_task(
            history_id,
            task_id,
            status="in_progress",
        )
        
        await event_pipe.post_event(
            event=AgentCommonEvent.INFO,
            target=target,
            data={
                "event_name": "on_team_task_in_progress",
                "content": {
                    "task_id": task_id
                }
            }
        )


    async def mark_completed(
        self,
        history_id: str,
        task_id: str,
    ):
        target = await self._update_task(
            history_id,
            task_id,
            status="completed",
            finish_timestamp=int(time.time()),
        )

        await self._emit_task_event(
            event=AgentCommonEvent.INFO,
            event_name="on_team_task_completed",
            history_id=history_id,
            task_id=task_id,
            target=target,
        )

        await self._emit_generation_completed_if_needed(
            history_id,
            task_id,
            target,
        )


    async def mark_failed(
        self,
        history_id: str,
        task_id: str,
        error: str,
    ):
        target = await self._update_task(
            history_id,
            task_id,
            status="failed",
            errors=error,
            finish_timestamp=int(time.time()),
        )

        await self._emit_task_event(
            event=AgentCommonEvent.ERROR,
            event_name="on_team_task_failed",
            history_id=history_id,
            task_id=task_id,
            target=target,
        )

        await self._emit_generation_completed_if_needed(
            history_id,
            task_id,
            target,
        )


    async def mark_cancelled(
        self,
        history_id: str,
        task_id: str,
        reason: str | None = None,
    ):
        updates = {
            "status": "cancelled",
            "finish_timestamp": int(time.time()),
        }

        if reason:
            updates["errors"] = reason

        target = await self._update_task(
            history_id,
            task_id,
            **updates,
        )

        await self._emit_task_event(
            event=AgentCommonEvent.WARNING,
            event_name="on_team_task_cancelled",
            history_id=history_id,
            task_id=task_id,
            target=target,
        )

        await self._emit_generation_completed_if_needed(
            history_id,
            task_id,
            target,
        )


    async def _emit_task_event(
        self,
        *,
        event: AgentCommonEvent,
        event_name: str,
        history_id: str,
        task_id: str,
        target=None,
    ):
        generation_id = self.task_generation.get(task_id)

        await event_pipe.post_event(
            event=event,
            target=target,
            data={
                "event_name": event_name,
                "content": {
                    "task_id": task_id,
                    "generation_id": generation_id,
                    "history_id": history_id.replace("sub_", ''),
                }
            }
        )
        

    async def _finish_generation_task(
        self,
        task_id: str,
    ):
        async with self._state_lock:
            generation_id = self.task_generation.pop(task_id, None)

            if not generation_id:
                return False, None

            task_ids = self.generation_tasks.get(generation_id)

            if not task_ids:
                return False, generation_id

            task_ids.discard(task_id)

            if not task_ids:
                self.generation_tasks.pop(generation_id, None)
                return True, generation_id

            return False, generation_id
        

    async def _emit_generation_completed_if_needed(
        self,
        history_id: str,
        task_id: str,
        target=None,
    ):
        """
        Emit generation completed event if all tasks in the generation
        have finished.
        """

        generation_finished, generation_id = (
            await self._finish_generation_task(task_id)
        )

        if not generation_finished:
            return

        await event_pipe.post_event(
            event=AgentCommonEvent.INFO,
            target=target,
            data={
                "event_name": "on_generation_team_task_completed",
                "content": {
                    "generation_id": generation_id,
                    "history_id": history_id.replace("sub_", ''),
                }
            }
        )


team_task_manager = TeamTaskManager()