import asyncio
import time
from typing import Callable, List, Awaitable, Union, Optional
from functools import wraps


from apix.common.lifespan.auto_init import auto_init
from apix.common.utils.logger import logger
from apix.config.base_config import CACHE_CLEAN_INTERVAL


class ResourceCleaner:
    """
    Global resource cleaner (singleton).

    Features:
        - Centralized cleanup scheduler
        - Supports async / sync cleanup functions
        - Auto registration via decorator
        - Fault isolation between cleanup tasks
    """

    _instance = None

    def __new__(cls):
        # Singleton
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Registered cleanup functions
        self._cleaners: List[Callable[[], Union[int, Awaitable[int]]]] = []

        # Background task
        self._task: Optional[asyncio.Task] = None

        # Default interval (seconds)
        self._interval = CACHE_CLEAN_INTERVAL

        # Running flag
        self._running = False

    # -----------------------------
    # Registration
    # -----------------------------

    def register(self, func: Callable):
        """
        Register a cleanup function manually.

        Args:
            func: Function returning int or Awaitable[int]
        """
        if func not in self._cleaners:
            self._cleaners.append(func)
            logger.debug(f"Registered: {func.__name__}")

    def auto_clear(self, func: Callable):
        """
        Decorator to auto-register a cleanup function.

        Usage:
            @cleaner.auto_clear
            async def clean_xxx():
                return removed_count
        """

        self.register(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    # -----------------------------
    # Lifecycle
    # -----------------------------

    async def start(self):
        """
        Start background cleanup loop.

        Args:
            interval: Cleanup interval in seconds
        """
        interval = CACHE_CLEAN_INTERVAL or 30

        if self._running:
            return

        self._interval = interval
        self._running = True

        self._task = asyncio.create_task(self._loop(), name="resource-cleaner")


    async def stop(self):
        """
        Stop background cleanup loop.
        """
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

            self._task = None


    # -----------------------------
    # Core loop
    # -----------------------------

    async def _loop(self):
        """
        Background loop.
        """
        try:
            while self._running:
                await asyncio.sleep(self._interval)
                await self.run_once()
        except asyncio.CancelledError:
            logger.debug("Cleanup loop cancelled")

    async def run_once(self):
        """
        Execute all cleanup functions once.
        """
        if not self._cleaners:
            return

        total_removed = 0

        for func in list(self._cleaners):
            try:
                result = func()

                # Support async + sync
                if asyncio.iscoroutine(result):
                    result = await result

                if isinstance(result, int):
                    total_removed += result

            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")

        if total_removed:
            logger.info(f"Cleaned total={total_removed}")


# Global singleton
resource_cleaner = ResourceCleaner()

auto_init.register(resource_cleaner)