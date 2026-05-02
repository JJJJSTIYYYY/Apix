import asyncio
from typing import Callable, List, Awaitable, Union

from apix_agent.commons.logger import logger


class AutoInit:
    """
    Global auto initializer (singleton).

    Features:
        - Centralized init execution
        - Supports async / sync functions
        - Auto registration via decorator
        - start(): execute all init functions once
        - stop(): execute all stop functions (reverse order)
    """

    _instance = None

    def __new__(cls):
        # Singleton
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Registered init / stop functions
        self._inits: List[Callable[[], Union[None, Awaitable[None]]]] = []
        self._stops: List[Callable[[], Union[None, Awaitable[None]]]] = []

        # Started flag
        self._started = False

    # -----------------------------
    # Registration
    # -----------------------------

    def register_init(self, func: Callable):
        if func not in self._inits:
            self._inits.append(func)
            logger.debug(f"[AutoInit] Registered init: {func.__name__}")

    def register_stop(self, func: Callable):
        if func not in self._stops:
            self._stops.append(func)
            logger.debug(f"[AutoInit] Registered stop: {func.__name__}")

    def auto_start(self, func: Callable):
        """
        Decorator to auto-register an init function.
        """
        self.register_init(func)
        return func

    def auto_stop(self, func: Callable):
        """
        Decorator to auto-register a stop function.
        """
        self.register_stop(func)
        return func

    # -----------------------------
    # Lifecycle
    # -----------------------------

    async def start(self):
        """
        Execute all init functions once.
        """
        if self._started:
            return

        self._started = True

        if not self._inits:
            logger.debug("[AutoInit] no init functions")
            return

        logger.info("[AutoInit] starting...")

        for func in list(self._inits):
            try:
                result = func()

                # Support async + sync
                if asyncio.iscoroutine(result):
                    await result

                logger.debug(f"[AutoInit] executed init: {func.__name__}")

            except Exception as e:
                logger.error(f"[AutoInit] error in init {func.__name__}: {e}")

        logger.info("[AutoInit] all init functions executed")

    async def stop(self):
        """
        Execute all stop functions (reverse order).
        """
        if not self._stops:
            logger.debug("[AutoInit] no stop functions")
            return

        logger.info("[AutoInit] stopping...")

        for func in reversed(self._stops):
            try:
                result = func()

                # Support async + sync
                if asyncio.iscoroutine(result):
                    await result

                logger.debug(f"[AutoInit] executed stop: {func.__name__}")

            except Exception as e:
                logger.error(f"[AutoInit] error in stop {func.__name__}: {e}")

        logger.info("[AutoInit] all stop functions executed")

        self._started = False


auto_init = AutoInit()