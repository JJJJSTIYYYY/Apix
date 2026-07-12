import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from apix_agent.commons.logger import logger


class AutoInit:
    """
    Global auto initializer (singleton).

    Registered objects must implement:
        - async start(...)
        - async stop(...)

    Registered task loops must be async functions without arguments.
    They will be started automatically in the background when start()
    is called and cancelled when stop() is called.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Avoid reinitializing singleton
        if getattr(self, "_initialized", False):
            return

        self._services: list[Any] = []

        # Registered background task loops
        self._task_loops: list[Callable[[], Awaitable[Any]]] = []

        # Running asyncio tasks
        self._running_tasks: list[asyncio.Task] = []

        self._started = False
        self._initialized = True

    # -----------------------------
    # Registration
    # -----------------------------

    def register(self, service: Any):
        """
        Register a lifecycle service.

        Service must provide:
            - async start()
            - async stop()
        """
        if service in self._services:
            return

        if not hasattr(service, "start"):
            raise AttributeError(
                f"{service.__class__.__name__} missing start() method"
            )

        if not hasattr(service, "stop"):
            raise AttributeError(
                f"{service.__class__.__name__} missing stop() method"
            )

        self._services.append(service)

        logger.debug(
            f"Registered service: {service.__class__.__name__}"
        )

    def register_as_task_loop(
        self,
        func: Callable[[], Awaitable[Any]],
    ) -> Callable[[], Awaitable[Any]]:
        """
        Register a background task loop.

        Can be used as a decorator:

            @auto_init.register_as_task_loop
            async def worker():
                while True:
                    ...
        """
        if func in self._task_loops:
            return func

        self._task_loops.append(func)

        logger.debug(
            f"Registered task loop: {func.__name__}"
        )

        return func

    # -----------------------------
    # Lifecycle
    # -----------------------------

    async def start(self):
        """
        Start all registered services once.
        """
        if self._started:
            return

        self._started = True

        if not self._services and not self._task_loops:
            logger.debug("Nothing to start")
            return

        logger.info("Starting...")

        # Start lifecycle services
        for service in self._services:
            try:
                await service.start()

                logger.debug(
                    f"Started: {service.__class__.__name__}"
                )

            except Exception as e:
                logger.exception(
                    f"Error starting "
                    f"{service.__class__.__name__}: {e}"
                )

        # Start background task loops
        for func in self._task_loops:
            try:
                task = asyncio.create_task(
                    func(),
                    name=f"AutoInit:{func.__name__}",
                )

                self._running_tasks.append(task)

                logger.debug(
                    f"Started task loop: {func.__name__}"
                )

            except Exception as e:
                logger.exception(
                    f"Error starting task loop "
                    f"{func.__name__}: {e}"
                )

        logger.success("All services started")

    async def stop(self):
        """
        Stop all registered services in reverse order.
        """
        if (
            not self._services
            and not self._running_tasks
        ):
            logger.debug("Nothing to stop")
            return

        logger.info("Stopping...")

        # Cancel background task loops
        for task in self._running_tasks:
            task.cancel()

        if self._running_tasks:
            await asyncio.gather(
                *self._running_tasks,
                return_exceptions=True,
            )

            self._running_tasks.clear()

        # Stop lifecycle services
        for service in reversed(self._services):
            try:
                await service.stop()

                logger.debug(
                    f"Stopped: {service.__class__.__name__}"
                )

            except Exception as e:
                logger.exception(
                    f"Error stopping "
                    f"{service.__class__.__name__}: {e}"
                )

        logger.success("All services stopped")

        self._started = False


auto_init = AutoInit()