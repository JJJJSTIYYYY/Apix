import asyncio
import uuid
from typing import Any, Dict, Callable

from apix.agent.store.core.execute_layer import DataExecutors
from apix.agent.store.core.mysql_server import mysql_server, MysqlService
from apix.agent.store.core.redis_server import redis_server, RedisService
from apix.common.utils.logger import logger
from apix.config.base_config import WORKER_COUNT


class DataServerManager:

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
        logger.trace()
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
        logger.trace()
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
        logger.info(f"Worker {worker_id} started")

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
                    f"Worker {worker_id}, action `{action}` error: {e}"
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

