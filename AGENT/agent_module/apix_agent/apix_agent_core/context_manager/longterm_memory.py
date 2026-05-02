import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AIMessageChunk, AnyMessage

from apix_agent.commons.auto_init import auto_init
from apix_agent.commons.type_def import AgentConfigSchema
from apix_agent.apix_agent_core.LLM import llm_factory as lf
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.commons.logger import logger


MEMORY_AGENT_PROMPT = (
    "You are a Long-Term Memory manager for an AI agent.\n\n"
    "You MUST output JSON that can be directly used by json.dumps in python ONLY.\n"
    "You MUST strictly follow the output schema below."
    "DO NOT add, remove, rename, or nest fields.\n\n"
    "--- Output Schema ---\n"
    "{\n"
    '  \"updates\": [\n'
    "    {\n"
    '      \"action\": \"insert\",    // Add a new memory that does not exist.\n'
    '      \"type\": \"preference | fact | rule | event | transient\",\n'
    '      \"confidence\": 0.0,\n'
    '      \"worth\": 0.0,\n'
    '      \"content\": \"<string>\"\n'
    "    },\n"
    "    {\n"
    '      \"action\": \"modify\",    // Update content of an existing memory.\n'
    '      \"target_id\": \"<ulid>\",\n'
    '      \"type\": \"preference | fact | rule | event | transient\",\n'
    '      \"confidence\": 0.0,\n'
    '      \"content\": \"<string>\"\n'
    "    },\n"
    "    {\n"
    '      \"action\": \"deprecate\",    // Mark an existing memory as deprecated.\n'
    '      \"target_id\": \"<ulid>\",\n'
    '      \"confidence\": 0.0,\n'
    '      \"reason\": \"<string>\"\n'
    "    },\n"
    "    {\n"
    '      \"action\": \"refresh\",    // Refresh timestamp of a memory (WILL be used but unchanged).\n'
    '      \"target_id\": \"<ulid>\",\n'
    '      \"confidence\": 0.0,\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "--- Rules ---\n"
    # "- Only use information explicitly stated or strongly implied by USER messages in delta_messages.\n"
    # "- Do NOT infer or restate information solely from existing_memory.\n\n"
    # "- Use insert when:\n"
    # "  a) The USER states new information that does not overlap with any existing memory, AND\n"
    # "  b) No existing memory needs to be deprecated as a result.\n"
    # "  Do NOT use insert to represent negations.\n\n"
    # "- Use modify when:\n"
    # "  a) The USER states information that already exists in existing_memory with the same meaning.\n"
    # "  b) The goal is to refresh or reaffirm an existing memory, even if the content does not change.\n\n"
    # "- Use deprecate when:\n"
    # "  a) The USER explicitly contradicts a prior memory, OR\n"
    # "  b) Two or more existing active memories are mutually contradictory.\n"
    # "  In conflict cases, deprecate the outdated or less reliable memory.\n"
    # "  If BOTH 'modify' and 'deprecate' conditions match, USE 'deprecate'.\n\n"
    # "- Prefer 'modify' and 'deprecate' than 'insert'.\n"
    "- For AI message, you should ONLY extract what has the ai done."
    "- At most ONE peice of memory may exist for the same mutually exclusive fact.\n"
    "- confidence and worth must be a float number between 0 ~ 1.\n"
    "- If no update or refresh is required, return exactly: { \"updates\": [] }.\n"
    "- No explanations, comments, or extra text."
)


class LongtermMemoryManager:
    """
    Asynchronous long-term memory summarization manager.

    - Memory summary runs in background tasks
    - Uses asyncio.Queue + to_thread to avoid blocking agent graph
    - Pending tasks are persisted in Redis to survive process restarts
    """

    REDIS_KEY = "longterm_memory:pending_tasks"

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        worker_concurrency: int = 1,
    ):
        self._redis = redis_client or redis.from_url(
            "redis://localhost:6378",
            decode_responses=True,
            socket_keepalive=True,
        )

        self._worker_concurrency = worker_concurrency
        self._queue: Optional[asyncio.Queue] = None
        self._workers: List[asyncio.Task] = []

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        Initialize internal queue and restore pending tasks from Redis.
        Must be called explicitly after event loop is ready.
        """
        if self._queue is not None:
            return

        self._queue = asyncio.Queue()

        # Restore pending tasks from Redis
        raw_tasks = await self._redis.hgetall(self.REDIS_KEY)
        for _, raw in raw_tasks.items():
            try:
                task = json.loads(raw)
                await self._queue.put(task)
                logger.info(
                    f"[LongtermMemory] Restore task "
                    f"(task_id={task.get('task_id')}, client_id={task.get('client_id')})"
                )
            except Exception as e:
                logger.error(f"[LongtermMemory] Failed to restore task: {e}")

        # Start background workers
        for _ in range(self._worker_concurrency):
            worker = asyncio.create_task(self._worker_loop())
            self._workers.append(worker)

    async def stop(self) -> None:
        """
        Gracefully stop workers (best-effort).
        """
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        self._queue = None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def submit_memory(
        self,
        client_id: str,
        delta_messages: Dict[str, Any],
        existing_memory: List[Dict[str, Any]],
        config: AgentConfigSchema,
    ) -> None:
        """
        Submit a long-term memory summarization task.
        This method is non-blocking for the agent graph.
        """
        if self._queue is None:
            raise RuntimeError("LongtermMemoryManager.start() must be called first")

        filtered_delta = self._filter_delta_message(delta_messages)
        if not filtered_delta:
            return

        task_id = str(uuid.uuid4())

        task = {
            "task_id": task_id,
            "client_id": client_id,
            "delta_messages": filtered_delta,
            "existing_memory": existing_memory,
            "config": config,
        }

        # Persist task to Redis before enqueueing
        await self._redis.hset(self.REDIS_KEY, task_id, json.dumps(task))

        await self._queue.put(task)

    # ------------------------------------------------------------------
    # worker
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        """
        Background worker loop.
        """
        assert self._queue is not None

        while True:
            task = await self._queue.get()
            try:
                await self._handle_task(task)
                self._queue.task_done()

            except asyncio.CancelledError:
                # Put task back to queue to avoid losing it
                await self._queue.put(task)
                self._queue.task_done()
                raise

            except Exception as e:
                logger.error(
                    f"[LongtermMemory] Task failed "
                    f"(task_id={task.get('task_id')}, client_id={task.get('client_id')}): {e}"
                )
                self._queue.task_done()

    async def _handle_task(self, task: Dict[str, Any]) -> None:
        """
        Handle a single memory summary task.
        """
        task_id = task["task_id"]

        try:
            # Run blocking LLM audit in a worker thread
            memory_update_dict = await asyncio.to_thread(
                self._run_memory_audit,
                task,
            )

            # Async call must stay in event loop
            if memory_update_dict:
                await ai_context_manager.update_longterm_memory(
                    task["client_id"],
                    memory_update_dict,
                )
                logger.info(
                    f"[LongtermMemory] Memory updated "
                    f"(task_id={task_id}, client_id={task['client_id']})"
                )

        except Exception as e:
            logger.error(
                f"[LongtermMemory] Handle task failed "
                f"(task_id={task_id}, client_id={task.get('client_id')}): {e}"
            )

        finally:
            # Always remove task from redis
            await self._redis.hdel(self.REDIS_KEY, task_id)

    # ------------------------------------------------------------------
    # LLM logic (sync, runs in to_thread)
    # ------------------------------------------------------------------

    def _run_memory_audit(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Run memory auditor LLM synchronously.

        This method is executed inside asyncio.to_thread,
        so it MUST NOT contain any async / await logic.
        """
        try:
            provider = task["config"].get("models_provider")
            model = task["config"].get("model_name")
            api_key = task["config"].get("api_key", "")

            llm = lf.get_llm_node(
                provider=provider,
                model=model,
                api_key=api_key,
            )

            messages = self._build_audit_prompt(
                delta_messages=task["delta_messages"],
                existing_memory=task["existing_memory"],
            )

            response = llm.invoke(messages)
            content = response.content

            # print("update_content: ", content)
            # Parse LLM output
            return json.loads(content)
        

        except Exception as e:
            logger.error(
                f"[LongtermMemory] Run memory audit failed "
                f"(task_id={task.get('task_id')}, client_id={task.get('client_id')}): {e}"
            )
            return None

    # ------------------------------------------------------------------
    # prompt
    # ------------------------------------------------------------------

    def _build_audit_prompt(
        self,
        delta_messages: List[Dict[str, Any]],
        existing_memory: List[Dict[str, Any]],
    ) -> List[Any]:
        """
        Build memory auditor prompt using SystemMessage + HumanMessage.
        """
        system_prompt = SystemMessage(content=MEMORY_AGENT_PROMPT)

        payload = {
            "messages": delta_messages,
            "existing_memory": existing_memory,
        }

        # print("existing_memory: ", existing_memory)

        human_prompt = HumanMessage(
            content=json.dumps(payload, ensure_ascii=False, indent=2)
        )

        return [system_prompt, human_prompt]

    def _filter_delta_message(
        self,
        delta_messages: List[AnyMessage | dict],
    ) -> List[Dict[str, Any]]:
        """
        Filter delta messages for long-term memory auditing.

        Only user-originated messages are considered reliable sources
        for long-term memory extraction.
        """
        filtered_msgs = []
        for msg in delta_messages:
            if isinstance(msg, AIMessage) or isinstance(msg, AIMessageChunk):
                filtered_msgs.append({
                    "role": "ai",
                    "content": msg.content,
                })
            elif isinstance(msg, HumanMessage):
                filtered_msgs.append({
                    "role": "user",
                    "content": msg.content,
                })
            elif isinstance(msg, dict):
                filtered_msgs.append({
                    "role": msg.get("role"),
                    "content": msg.get("content"),
                })

            return filtered_msgs


longterm_memory_manager = LongtermMemoryManager()


@auto_init.auto_start
async def start_longterm_memory_manager():
    await longterm_memory_manager.start()


@auto_init.auto_stop
async def stop_longterm_memory_manager():
    await longterm_memory_manager.stop()



'''
docker run -d \
  --name redis-longterm-memory \
  -p 6378:6379 \
  -v ./data/redis/data-6380:/data \
  redis:7
'''