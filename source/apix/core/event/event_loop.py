import asyncio
from datetime import datetime
import traceback

from apix.config.base_config import SHOW_EVENT_DISPATCH
from apix.core.event.base import ApixEventHandler, ApixEvent
from apix.core.event.handler_registry import (
    ApixHandlerRegistry,
    APIX_HANDLER_REGISTRY,
)
from apix.core.event.event_pipe import EVENT_PIPE
from apix.common.utils.logger import logger


# =========================
# Common Event Handler
# =========================
class ApixEventLoop:

    def __init__(
        self,
        registry: ApixHandlerRegistry,
    ):
        self._registry = registry

        self._event_consumer_task: asyncio.Task | None = None

        self._dispatch_tasks: set[asyncio.Task] = set()
        self._dispatch_semaphore = asyncio.Semaphore(100) # back pressure

        self._background_handler_tasks: set[asyncio.Task] = set()
        self._background_handler_semaphore = asyncio.Semaphore(100)

        self.started = False

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
            self.started = True
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
                await self._dispatch_semaphore.acquire()

                try:
                    event: ApixEvent = await EVENT_PIPE.get()
                    if SHOW_EVENT_DISPATCH:
                        event_name_block = event.event_name
                        handler_chain_version = event._handler_chain_version
                        current_chain_version = APIX_HANDLER_REGISTRY.get_current_version_for_event_without_resolve(event_name_block)
                        print(f"\033[38;5;59m{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\033[0m"
                            f" \033[1;38;5;147m[EVENT LOOP]\033[0m"
                            f" \033[38;5;59m│\033[0m"
                            f" \033[38;5;116m{event_name_block}\033[0m"
                            f" \033[38;5;59m│\033[0m"
                            f" \033[38;5;152m{handler_chain_version}\033[0m"
                            f"\033[38;5;240m→\033[0m"
                            f"\033[48;5;235;38;5;110m {current_chain_version} \033[0m"
                        )
                except BaseException:
                    self._dispatch_semaphore.release()
                    raise

                # Dispatch event to handler without blocking.
                task = asyncio.create_task(
                    self._dispatch_event_and_ack(event),
                )

                self._dispatch_tasks.add(task)

                task.add_done_callback(
                    self._dispatch_tasks.discard
                )

        except asyncio.CancelledError:
            logger.info("Event loop cancelled.")

    async def _dispatch_event_and_ack(self, event: ApixEvent) -> ApixEvent | None:
        """Dispatch one event and complete the builtin queue task."""
        try:
            return await self._dispatch_event(event)
        finally:
            EVENT_PIPE.task_done()

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
        handler: ApixEventHandler,
        event: ApixEvent,
    ):
        """
        Execute background handler safely.
        """

        try:
            async with self._background_handler_semaphore:
                if handler.time_out is None:
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

            handler_chain = self._registry.get_handlers_chain_for_event(
                event.event_name,
                event._handler_chain_version,
            )

            if not handler_chain:
                return event

            for handler_name in handler_chain:
                if event.accepted:
                    break

                # A permanently deleted entry cannot be resolved. This should
                # only occur when callers delete a handler while an older event
                # version is still queued.
                handler = self._registry.get_handler(handler_name)
                if handler is None:
                    logger.warning(
                        f"Handler missing from registry: {handler_name}, "
                        f"event={event.event_name}"
                    )
                    continue

                try:
                    if handler.background:
                        self._create_background_handler_task(
                            handler,
                            event,
                        )
                    else:
                        if handler.time_out is None:
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


APIX_EVENT_LOOP = ApixEventLoop(APIX_HANDLER_REGISTRY)

__all__ = ['APIX_EVENT_LOOP', 'ApixEventLoop']