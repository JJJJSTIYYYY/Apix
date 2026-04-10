import asyncio
import uuid
from typing import Any, Dict, Callable

from core.commons.logger import logger
from core.domain.mysql_server import mysql_server, MysqlService
from core.domain.redis_server import redis_server, RedisService
from core.domain.execute_layer import DataExecutors
from global_config import WORKER_COUNT


class DataServerManager:
    """
    Coordinate data storage between Redis (hot storage) and MySQL (persistent storage).

    Execution Model:
    ----------------
    DataServerManager acts as an asynchronous task dispatcher.

    - submit_query(...) only enqueues a query task and returns a query_id immediately.
    - Actual execution is performed by internal worker(s).
    - wait_result(query_id) blocks (awaits) until:
        * the task finishes successfully
        * or fails with an exception

    Responsibility Boundary:
    ------------------------
    - DataServerManager:
        * Route action to RedisService / MysqlService
        * Control execution order and concurrency
        * Normalize return format (success / fail / payload)

    - RedisService / MysqlService:
        * Do NOT coordinate with each other
        * Do NOT know task orchestration logic

    This manager implements a two-level memory architecture:
    -------------------
    - Redis:
        * Stores the latest conversation messages and task infromation (actived) for fast access and update.
        * Only the most recent MAX_MEMO_LEN messages in one conversation (default: 100) are kept in total (managed by RedisService).
        * Acts as the first lookup/insert layer when retrieving messages and create or update task info.
        * Messages in redis is the full window that can be seen by AI.

    - MySQL:
        * Stores the full and permanent dialog history and task information.
        * Acts as the only source of truth for all conversation messages.
        * Do NOT receive messages evicted from Redis. Redis is only the cache for messages.
        * Do receive task (tool calling) info evicted from Redis when task is finished and only store the finished task info.
        * Acts as the first insert layer when append message.

    Data Flow Overview:
    -------------------
    1. Append Message:
        - Append message to MySQL and try to backfill to redis (RedisService.append_messages).
            - If target conversation messages cache not exists in redis, skip.
            - Else append to tail.

    2. Get Messages:
        - Attempt to read conversation messages from Redis first.
        - If missing, load the required history from MySQL into Redis (RedisService.backfill_messages),
          then return the result.

    3. Create Task:
        - Allow tools service to create task if task_hash not exist in redis.
        - Return fail: "task already exists." if task_hash already exist.

    4. Update Task:
        - If task_hash exist in redis:
            - Allow tools service to update task info to redis.
            - RedisService check the task status, if finished, delete and return the full task info.
            - If get full task info, insert into mysql.
        - If task_hash not exist in redis:
            - Return fail: "task is not running." if task_hash not exist in redis.

    5. Get Task info:
        - If task_hash exist in redis, get and return.
        - If task_hash not exist in redis:
            - If task_id in mysql: get and return.
            - Else return task not found.

    Return Contract:
    ----------------
    - All handlers return a dict with at least:
        * success: bool
        * messages: payload or error description
    - Exceptions are caught and converted to success = False.
    - An empty dict in messages represents logical not-found, not an error.


    Handlers in RedisService & MysqlService Overview:
    -------------------
    RedisService: 
        - redis.memo.append_messages: Called after append message to mysql, this handler will try to fill back (append) new message to redis.
        - redis.memo.get_recent_messages: Get messages after last_cursor(include) from redis and return result contains cache_hit(bool), next_cursor(int), messages(list) and so on.
        - redis.memo.backfill_messages: Called after messages missed from redis and query mysql, this method will fill back messages to redis and set TTL.
        - redis.task.create_task: Try to create task info in redis and set TTL, return fail if task is already running.
        - redis.task.update_task: Try to update task info in redis, return fail if task not found.
        - redis.task.get_task_info: Try to get task info in redis, if not exist, return {}, if error occured, return fail.
        - redis.common.set_expire: Try to set TTL for target key.
    MysqlService:
        - mysql.user.ensure_user_exists: Ensure user exist in mysql, and update some user info.
        - mysql.memo.fetch_conversation_list: Get conversation list to display in client's conversations history dock panel.
        - mysql.memo.create_conversation: Create a new conversation when user clicked the "Plus Btn" on conversations history docker pennel.
        - mysql.memo.append_message: Append a new message to mysql and do nothing else.
        - mysql.memo.fetch_messages_after_cursor: Get messages after cursor in mysql.
        - mysql.task.insert_task_result: Insert finished task info (done/fail) into mysql.
        - mysql.task.fetch_task_info: Get task info from mysql. Return {} if not found.
    """

    def __init__(
        self,
        *,
        redis_store: RedisService,
        mysql_store: MysqlService,
        worker_count: int = 4,
    ):
        self._redis = redis_store
        self._mysql = mysql_store

        # Execution layer
        self.executor = DataExecutors(
            redis_store=self._redis,
            mysql_store=self._mysql,
        )

        # Action -> executor handler
        self._handle: Dict[str, Callable] = {}

        # Register handler
        handler_dict = self.executor.export_handlers()
        for action, handler in handler_dict.items():
            self.handle_register(action, handler)

        # Task queue & result futures
        self._queue: asyncio.Queue = asyncio.Queue()
        self._results: Dict[str, asyncio.Future] = {}

        self._worker_count = worker_count

        # Start workers
        self._workers = [
            asyncio.create_task(self._worker_loop(worker_id))
            for worker_id in range(worker_count)
        ]

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------
    def handle_register(self, task_type: str, handler: Callable) -> None:
        """
        Register a task handler.
        """
        self._handle[task_type] = handler


    async def submit_query(self, action: str, payload: dict) -> str:
        """
        Submit a query task.

        Returns:
            query_id (uuid string)
        """
        logger.info("[DataServerManager][submit_query] enter.")
        query_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self._results[query_id] = future
        await self._queue.put((query_id, action, payload))
        return query_id

    async def wait_result(self, query_id: str) -> Any:
        """
        Wait for task result.
        """
        logger.info("[DataServerManager][wait_result] enter.")
        future = self._results.get(query_id)
        if not future:
            raise KeyError(f"Unknown query_id: {query_id}")

        try:
            return await future
        finally:
            # Ensure cleanup
            self._results.pop(query_id, None)
    

    # --------------------------------------------------
    # Worker Loop
    # --------------------------------------------------

    async def _worker_loop(self, worker_id: int) -> None:
        """
        Worker loop.

        Fetch task from queue and execute corresponding handler.
        """
        logger.info(f"[DataServerManager][worker-{worker_id}] started")

        while True:
            query_id, action, payload = await self._queue.get()

            future = self._results.get(query_id)
            if not future:
                # Task already cancelled or cleaned
                self._queue.task_done()
                continue

            try:
                handler = self._handle.get(action)
                if not handler:
                    result = {
                        "success": False,
                        "messages": f"unknown action: {action}",
                    }
                else:
                    # Bind executor instance explicitly
                    result = await handler(payload)

            except Exception as e:
                # Executor layer should NOT raise, but double protection here
                logger.exception(
                    f"[DataServerManager][worker-{worker_id}] action = {action} error: {e}"
                )
                result = {
                    "success": False,
                    "messages": f"internal error: {e}",
                }

            # Complete future safely
            if not future.done():
                future.set_result(result)

            self._queue.task_done()




data_server_manager = DataServerManager(
    redis_store=redis_server,
    mysql_store=mysql_server,
    worker_count=WORKER_COUNT,
)

