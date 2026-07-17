import asyncio
import traceback

from apix.runtime.core.event.base import HandlerEntry, ApixEvent
from apix.runtime.core.event.event_registry import apix_event_registry
from apix.runtime.core.event.event_writer import event_pipe
from apix.runtime.core.event.event_registry import ApixEventRegistry
from apix.common.utils.logger import logger


# =========================
# Common Event Handler
# =========================
class ApixEventLoop:

    def __init__(
        self,
        registry: ApixEventRegistry,
    ):
        self._registry = registry

        self._event_consumer_task: asyncio.Task | None = None

        self._dispatch_tasks: set[asyncio.Task] = set()
        self._dispatch_semaphore = asyncio.Semaphore(100)

        self._background_handler_tasks: set[asyncio.Task] = set()
        self._background_handler_semaphore = asyncio.Semaphore(100)

    async def start(self):
        """
        Start event consumer worker.
        Safe to call multiple times.
        """

        if self._event_consumer_task is None:
            self._event_consumer_task = asyncio.create_task(
                self._event_consumer_loop(),
                name="pipe-event-consumer",
            )

            logger.info("Worker started.")

    async def stop(self):
        """
        Stop event consumer worker.
        """

        task = self._event_consumer_task

        if task:
            self._event_consumer_task = None

            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        dispatch_tasks = list(self._dispatch_tasks)

        for dispatch_task in dispatch_tasks:
            dispatch_task.cancel()

        if dispatch_tasks:
            await asyncio.gather(
                *dispatch_tasks,
                return_exceptions=True,
            )

        self._dispatch_tasks.clear()

        background_tasks = list(self._background_handler_tasks)

        for background_task in background_tasks:
            background_task.cancel()

        if background_tasks:
            await asyncio.gather(
                *background_tasks,
                return_exceptions=True,
            )

        self._background_handler_tasks.clear()

        logger.info("Worker stopped.")

    # Consumer
    async def _event_consumer_loop(self):
        """
        Serial event consumer.
        """

        logger.info("Event loop started.")

        try:
            while True:
                event = await event_pipe.get_event()

                await self._dispatch_semaphore.acquire()

                task = asyncio.create_task(
                    self._dispatch_event(event),
                )

                self._dispatch_tasks.add(task)

                task.add_done_callback(
                    self._dispatch_tasks.discard
                )

        except asyncio.CancelledError:
            logger.info("Event loop cancelled.")

    def _create_background_handler_task(
        self,
        handler,
        event: ApixEvent,
    ):
        task = asyncio.create_task(
            self._run_background_handler(
                handler,
                event,
            )
        )

        self._background_handler_tasks.add(task)

        task.add_done_callback(
            self._background_handler_tasks.discard
        )

    async def _run_background_handler(
        self,
        handler: HandlerEntry,
        event: ApixEvent,
    ):
        """
        Execute background handler safely.
        """

        try:
            async with self._background_handler_semaphore:
                if handler.time_out == -1:
                    await handler.callback(event)
                else:
                    await asyncio.wait_for(
                        handler.callback(event),
                        timeout=handler.time_out,
                    )

        except asyncio.TimeoutError:
            logger.error(
                f"Handler timeout: "
                f"event={event.event_name}, "
                f"handler={handler.callback.__name__}, "
            )

        except asyncio.CancelledError:
            raise

        except Exception as e:
            logger.error(
                f"Handler failed: "
                f"event={event.event_name}, "
                f"handler={handler.callback.__name__}, "
                f"error={type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}"
            )

    async def _dispatch_event(
        self,
        event: ApixEvent,
    ) -> ApixEvent | None:
        """
        Dispatch event to registered handlers.
        """

        try:
            if not event.event_name:
                return None

            handlers = self._registry.get_handlers(
                event.event_name
            )

            if not handlers:
                return event.

            for handler in handlers:
                if event.accepted:
                    break

                try:
                    if handler.background:
                        self._create_background_handler_task(
                            handler,
                            event,
                        )
                    else:
                        if handler.time_out == -1:
                            await handler.callback(event)
                        else:
                            await asyncio.wait_for(
                                handler.callback(event),
                                timeout=handler.time_out,
                            )

                    if event.accepted:
                        break

                except asyncio.TimeoutError:
                    logger.error(
                        f"Handler timeout: "
                        f"event={event.event_name}, "
                        f"handler={handler.callback.__name__}, "
                    )

                except Exception as e:
                    logger.error(
                        f"Handler failed: "
                        f"event={event.event_name}, "
                        f"handler={handler.callback.__name__}, "
                        f"error={type(e).__name__}: {e}\n"
                        f"{traceback.format_exc()}"
                    )

                    if handler.stop_when_error:
                        break

            event.accept()

            return event

        except Exception as e:
            logger.error(
                f"Dispatch failed: "
                f"{type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}"
            )

        finally:
            self._dispatch_semaphore.release()


apix_event_loop = ApixEventLoop(apix_event_registry)