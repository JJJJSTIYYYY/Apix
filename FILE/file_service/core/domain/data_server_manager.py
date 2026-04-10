import asyncio
import uuid
from typing import Any, Dict, Callable

from core.commons.logger import logger
from core.domain.mysql_server import mysql_server, MysqlService
from core.domain.milvus_server import milvus_server, MilvusService
from core.domain.file_server import file_server, FileService
from core.domain.execute_layer import DataExecutors
from global_config import WORKER_COUNT


class DataServerManager:
    """
    MySQL (persistent storage).
    """

    def __init__(
        self,
        *,
        mysql_store: MysqlService,
        milvus_store: MilvusService,
        file_store: FileService,
        worker_count: int = 4,
    ):
        self._mysql = mysql_store
        self._milvus = milvus_store
        self._file = file_store

        # Execution layer
        self.executor = DataExecutors(
            mysql_store=self._mysql,
            milvus_store=self._milvus,
            file_store=self._file,
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
    mysql_store=mysql_server,
    milvus_store=milvus_server,
    file_store=file_server,
    worker_count=WORKER_COUNT,
)
