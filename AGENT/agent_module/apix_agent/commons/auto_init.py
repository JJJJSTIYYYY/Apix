from typing import Any, List

from apix_agent.commons.logger import logger


class AutoInit:
    """
    Global auto initializer (singleton).

    Registered objects must implement:
        - async start(...)
        - async stop(...)
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

        self._services: List[Any] = []
        self._started = False
        self._initialized = True

    # -----------------------------
    # Registration
    # -----------------------------

    def register(self, service: Any):
        """
        Register a lifecycle service.

        Service must provide:
            - start()
            - stop()
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

        if not self._services:
            logger.debug("No services")
            return

        logger.info("Starting...")

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

        logger.success("All services started")

    async def stop(self):
        """
        Stop all registered services in reverse order.
        """
        if not self._services:
            logger.debug("No services")
            return

        logger.info("Stopping...")

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