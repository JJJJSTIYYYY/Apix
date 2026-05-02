import traceback
from typing import AsyncIterator, Any
import time
import asyncio

from langgraph.graph.state import CompiledStateGraph

from apix_agent.commons.auto_init import auto_init
from apix_agent.apix_agent_core.agent_factory.agent_creator import agent_creator
from apix_agent.apix_agent_core.agent_team_task.task_manager import task_manager
from apix_agent.commons.type_def import MainAgentState, SubAgentState, AgentConfigSchema
from apix_agent.commons.logger import logger

class AgentRuningtime:

    def __init__(self):
        # Sub-agent worker
        self._sub_agent_worker_task: asyncio.Task | None = None
        self._sub_agent_stop_task: asyncio.Task | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}

        self.agent_config: dict = {}
    
    #-----------------------------------------------------------------------
    # Lifespan
    #-----------------------------------------------------------------------

    async def start(self):
        """
        Start background tasks.
        Safe to call multiple times.
        """

        if self._sub_agent_stop_task is None:
            self._sub_agent_stop_task = asyncio.create_task(
                self.stop_sub_agent(),
                name="sub-agent-stopper",
            )
            logger.info("[stop_sub_agent] Worker started.")

        if self._sub_agent_worker_task is None:
            self._sub_agent_worker_task = asyncio.create_task(
                self._sub_agent_worker_loop(),
                name="sub-agent-worker",
            )
            logger.info("[sub_agent_worker] Worker started.")


    async def stop(self):
        """
        Stop background tasks gracefully.
        """

        # Stop sub-agent stopper
        stopper = self._sub_agent_stop_task
        if stopper:
            self._sub_agent_stop_task = None
            stopper.cancel()
            try:
                await stopper
            except asyncio.CancelledError:
                pass
            logger.info("[stop_sub_agent] Worker stopped.")

        # Stop sub-agent worker
        worker = self._sub_agent_worker_task
        if worker:
            self._sub_agent_worker_task = None
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            logger.info("[sub_agent_worker] Worker stopped.")


    async def _run_sub_agent(
        self,
        agent_name: str,
        initial_state: SubAgentState,
        config: AgentConfigSchema,
    ):
        """
        Execute one sub-agent task.

        This runs in its own asyncio Task so multiple
        sub-agents can run concurrently.
        """
        agent = None

        try:

            agent = await agent_creator.create_sub_agent(agent_name, initial_state.get("agent_role"), config)

            if not isinstance(agent, CompiledStateGraph):
                logger.error(f"[sub_agent_worker] Create sub-agent failed: {agent}")
                return
            
            stream = agent.astream(
                initial_state,
                {"recursion_limit": 1024},
                stream_mode="custom",
            )

            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "in_progress")

            async for chunk in stream:
                if chunk.get("event") == "tool_exec_start":
                    tool_data = chunk.get("data", {})
                    if tool_data.get("tool_name", "") == "write_todos":
                        await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "todos", tool_data.get("content", []))
                elif chunk.get("event") == "ai_message_return":
                    msg_data = chunk.get("data", {})
                    if msg_data.get("event_name", "") == "output_chunk_rtn":
                        await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "outputs", msg_data.get("content", ""))

            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "completed")
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "finish_timestamp", int(time.time()))

        except asyncio.CancelledError:
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "cancelled")
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "finish_timestamp", int(time.time()))
            logger.info(f"[sub_agent_worker] Task stopped: {initial_state['task_id']}")

        except Exception as e:
            error_logs = traceback.format_exc()
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "finish_timestamp", int(time.time()))
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "errors", f"{type(e)}: {e}: {error_logs}")
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "failed")
            logger.error(f"[sub_agent_worker] Task execution failed: {type(e)}: {e}: {error_logs}")

        finally:
            # Remove from running task registry
            self._running_tasks.pop(initial_state["task_id"], None)
            if agent:
                agent_creator.done(agent)


    async def _sub_agent_worker_loop(self):
        """
        Background worker that dispatches sub-agent tasks.
        """

        logger.info("[sub_agent_worker] Started.")

        try:
            while True:
                agent_name, initial_state, config = await task_manager.task_queue.get()

                try:
                    task_id = initial_state.get("task_id")

                    if not task_id:
                        logger.error("[_sub_agent_worker_loop] No task_id provided in initial_state.")
                        raise RuntimeError("No task_id provided in initial_state.")

                    # Dispatch task
                    task = asyncio.create_task(
                        self._run_sub_agent(
                            agent_name,
                            initial_state,
                            config,
                        )
                    )

                    self._running_tasks[task_id] = task

                finally:
                    task_manager.task_queue.task_done()

        except asyncio.CancelledError:
            logger.info("[sub_agent_worker] Cancelled.")


    async def stop_sub_agent(self):
        """
        Background worker that handles stop requests for running sub-agent tasks.
        """
        logger.info("[sub_agent_stop_worker] Started.")

        try:
            while True:
                task_id = await task_manager.stop_request_queue.get()

                task = self._running_tasks.get(task_id)

                if not task:
                    logger.warning(f"[sub_agent_stop_worker] Task not found: {task_id}")
                    task_manager.stop_request_queue.task_done()
                    continue

                logger.info(f"[sub_agent_stop_worker] Cancelling task: {task_id}")

                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                task_manager.stop_request_queue.task_done()

        except asyncio.CancelledError:
            logger.info("[sub_agent_stop_worker] Cancelled.")
            

    #---------------------------------------------------------------
    # Streaming task API
    #---------------------------------------------------------------

    async def submit_agent_task(
        self,
        agent_role: MainAgentState | SubAgentState = None,
        agent_name: str = None,
        config: AgentConfigSchema = None,
    ) -> CompiledStateGraph:
        """
        Start a streaming agent execution.

        Args:
            initial_state: MainAgentState, TypedDict.
            config: dict, llm model config.

        Returns:
            Async iterator of LangGraph stream events.
        """
        logger.trace('[agent.py] [AI_Agent] [submit_task] Enter')

        agent = await agent_creator.create_agent(agent_name, agent_role, config)
        if not isinstance(agent, CompiledStateGraph):
            raise RuntimeError(
                f"Get agent error. Please make sure your config correct.\n\nDetail: {agent}"
            )
        logger.info(
            f"[submit_task] Start agent streaming: "
            f"{agent_role} - {agent_name}"
        )

        return agent
    
    
    async def done(self, agent_graph: CompiledStateGraph) -> None:
        """
        Mark a graph as done (no longer in active use).
        """
        if agent_graph:
            await agent_creator.done(agent_graph)
    


ai_agent = AgentRuningtime()

@auto_init.auto_start
async def start_ai_agent_runingtime():
    await ai_agent.start()


@auto_init.auto_stop
async def stop_ai_agent_runingtime():
    await ai_agent.stop()