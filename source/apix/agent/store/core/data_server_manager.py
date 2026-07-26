import asyncio
import uuid
from typing import Any, Dict, Callable

from apix.agent.store.core.execute_layer import DataExecutors
from apix.common.lifespan.auto_init import auto_init
from apix.common.utils.logger import logger
from apix.config.base_config import WORKER_COUNT, CACHE_STORE_TYPE, DATA_STORE_TYPE
from apix.agent.store.core.server.cache_store.cache_server_base import CacheServerBase
from apix.agent.store.core.server.data_store.data_server_base import DataServerBase

if CACHE_STORE_TYPE == 'redis':
    from apix.agent.store.core.server.cache_store.redis_server import cache_server
elif CACHE_STORE_TYPE == 'builtin':
    from apix.agent.store.core.server.cache_store.builtin_server import cache_server
else:
    raise NotImplementedError()

if DATA_STORE_TYPE == 'mysql':
    from apix.agent.store.core.server.data_store.mysql_server import data_server
elif DATA_STORE_TYPE == 'sqlite':
    from apix.agent.store.core.server.data_store.sqlite_server import data_server
else:
    raise NotImplementedError()

from apix.agent.store.core.server.file_store.file_server import FileService, file_server
from apix.agent.store.core.server.rag_store.rag_server import RagService, rag_server

class DataServerManager:

    def __init__(
        self,
        *,
        cache_store: CacheServerBase,
        data_store: DataServerBase,
        file_server: FileService,
        rag_server: RagService,
        worker_count: int = 4,
    ):
        # Execution layer
        self.executor = DataExecutors(
            cache_store=cache_store,
            data_store=data_store,
            file_server=file_server,
            rag_server=rag_server
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

        if worker_count < 1:
            raise ValueError("worker_count must be greater than zero")
        self._worker_count = worker_count
        # Workers start lazily. This keeps module import safe when no event loop
        # is running while still allowing submit_query() to work standalone.
        self._workers: list[asyncio.Task] = []

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def handle_register(self, task_type: str, handler: Callable) -> None:
        """
        Register a task handler.
        """
        self._handle[task_type] = handler


    async def start(self) -> None:
        """Start query workers once."""
        if self._workers:
            return

        self._workers = [
            asyncio.create_task(
                self._worker_loop(worker_id),
                name=f"data-server-worker-{worker_id}",
            )
            for worker_id in range(self._worker_count)
        ]


    async def stop(self) -> None:
        """Cancel workers and pending queries, leaving the manager restartable."""
        workers, self._workers = self._workers, []
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

        for future in self._results.values():
            if not future.done():
                future.cancel()
        self._results.clear()

        # Remove tasks that were queued but never picked up by a worker.
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._queue.task_done()


    async def submit_query(self, action: str, payload: dict) -> str:
        """
        Submit a query task.

        Returns:
            query_id (uuid string)
        """
        logger.trace()
        await self.start()
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
        if future is None:
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
            try:
                future = self._results.get(query_id)
                if future is None or future.done():
                    # Task already cancelled or cleaned.
                    continue

                handler = self._handle.get(action)
                if not handler:
                    result = {
                        "success": False,
                        "messages": f"unknown action: {action}",
                    }
                else:
                    # Bind executor instance explicitly
                    result = await handler(payload)

                # Complete future safely.
                if not future.done():
                    future.set_result(result)

            except Exception as e:
                # Executor layer should NOT raise, but double protection here.
                logger.exception(
                    f"Worker {worker_id}, action `{action}` error: {e}"
                )
                if not future.done():
                    future.set_result(
                        {
                            "success": False,
                            "messages": f"internal error: {e}",
                        }
                    )
            finally:
                self._queue.task_done()




data_server_manager = DataServerManager(
    cache_store=cache_server,
    data_store=data_server,
    file_server=file_server,
    rag_server=rag_server,
    worker_count=WORKER_COUNT,
)
auto_init.register(data_server_manager)


async def query_store(action: str, payload: dict) -> dict:
    """Public api to access stre."""
    query_id = await data_server_manager.submit_query(
        action=action,
        payload=payload,
    )
    result = await data_server_manager.wait_result(query_id)
    if not result.get("success"):
        logger.error(f"Failed to access store: {result.get("messages")}")