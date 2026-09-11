import asyncio
from datetime import datetime
import traceback

from apix.config.base_config import SHOW_EVENT_DISPATCH
from apix.core.event.base import ApixEvent
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
        self._dispatch_semaphore = asyncio.Semaphore(1000) # back pressure

        self._background_handler_tasks: set[asyncio.Task] = set()
        self._background_handler_semaphore = asyncio.Semaphore(1000)

        self.started = False

    def start_nowait(self) -> None:
        """Start the consumer in the running asyncio loop, once."""
        if self._event_consumer_task is None or self._event_consumer_task.done():
            self._event_consumer_task = asyncio.create_task(
                self._event_consumer_loop(), name="pipe-event-consumer",
            )
            self.started = True
            logger.info("Worker started.")

    async def start(self) -> None:
        """Start event consumption. Safe to call multiple times."""
        self.start_nowait()

    async def stop(self) -> None:
        """Stop consumption while queued events and dispatched calls remain.

        A subsequent local publication starts the consumer again. Dispatch and
        background tasks already scheduled are allowed to finish normally.
        """
        task = self._event_consumer_task
        self._event_consumer_task = None
        self.started = False
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
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
                except BaseException:
                    self._dispatch_semaphore.release()
                    raise

                try:
                    # Resolve synchronously after dequeue, before any task can
                    # observe later registration or ordering changes.
                    handler_chain = (
                        self._registry.get_handlers_chain_for_event(event.event_name)
                        if event.event_name else []
                    )
                    if SHOW_EVENT_DISPATCH:
                        event_name_block = event.event_name
                        print(f"\033[38;5;59m{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\033[0m"
                            f" \033[1;38;5;147m[EVENT LOOP]\033[0m"
                            f" \033[38;5;59m│\033[0m"
                            f" \033[38;5;116m{event_name_block}\033[0m"
                        )
                except Exception as exc:
                    # Resolution moved out of dispatch, so acknowledge failed
                    # events here and keep consuming subsequent queue items.
                    logger.error(
                        f"Handler chain resolution failed: {type(exc).__name__}: "
                        f"{exc}\n{traceback.format_exc()}"
                    )
                    EVENT_PIPE.task_done()
                    self._dispatch_semaphore.release()
                    continue

                # Dispatch event to handler without blocking.
                task = asyncio.create_task(
                    self._dispatch_event(event, handler_chain),
                )

                self._dispatch_tasks.add(task)

                task.add_done_callback(
                    self._on_dispatch_done
                )

        except asyncio.CancelledError:
            logger.info("Event loop cancelled.")

    def _on_dispatch_done(self, task: asyncio.Task) -> None:
        """Release queue ownership even when cancelled before coroutine entry."""
        self._dispatch_tasks.discard(task)
        try:
            EVENT_PIPE.task_done()
        finally:
            self._dispatch_semaphore.release()

        if not task.cancelled():
            error = task.exception()
            if error is not None:
                logger.error(
                    f"Dispatch task failed: {type(error).__name__}: {error}"
                )

    async def _create_background_handler_task(
        self,
        handler_name: str,
        event: ApixEvent,
    ):
        await self._background_handler_semaphore.acquire()

        coroutine = self._run_background_handler(handler_name, event)
        try:
            task = asyncio.create_task(coroutine)
        except BaseException:
            # Release capacity if task creation fails.
            coroutine.close()
            self._background_handler_semaphore.release()
            raise

        self._background_handler_tasks.add(task)
        task.add_done_callback(self._on_background_handler_done)

    async def _run_background_handler(
        self,
        handler_name: str,
        event: ApixEvent,
    ):
        """
        Execute background handler safely.
        """
        # Capacity may have required a wait. Resolve the current entry only
        # now and recheck its current subscription and exclusions.
        handler = self._registry.get_handler(handler_name)
        if handler is not None and self._registry._matches_handler(handler, event.event_name):
            await handler.execute(event)

    def _on_background_handler_done(self, task: asyncio.Task) -> None:
        # Also runs when the task is cancelled before its coroutine starts.
        self._background_handler_tasks.discard(task)
        self._background_handler_semaphore.release()

    async def _dispatch_event(
        self,
        event: ApixEvent,
        handler_chain: list[str],
    ) -> ApixEvent | None:
        """
        Dispatch event to registered handlers.
        """

        try:
            if not event.event_name:
                return None

            if not handler_chain:
                return event

            for handler_name in handler_chain:
                # Earlier handlers may await while subscriptions change.
                handler = self._registry.get_handler(handler_name)
                if handler is None or not self._registry._matches_handler(handler, event.event_name):
                    continue

                if handler.background:
                    await self._create_background_handler_task(handler_name, event)
                else:
                    await handler.execute(event)

            return event

        except Exception as e:
            logger.error(
                f"Dispatch failed: "
                f"{type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}"
            )


APIX_EVENT_LOOP = ApixEventLoop(APIX_HANDLER_REGISTRY)

__all__ = ['APIX_EVENT_LOOP', 'ApixEventLoop']