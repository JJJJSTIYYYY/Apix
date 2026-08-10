import asyncio
from collections.abc import Awaitable
from functools import wraps
from uuid import uuid4

from typing import Any, Callable

from apix.core.graph.context.manager import get_graph_context
from apix.core.event import (
    ApixEvent,
    EventType,
    apix_event_registry,
    event_pipe_writer,
)
from apix.core.graph.interrupter.base import Block


InterruptedHandler = Callable[[Block], Awaitable[None]]


async def interrupt(
    *,
    data: Any = None,
    timeout: float | None = None,
) -> Any:
    """
    Send data and while in graph loop and block the agent graph at the same time.
    Can be called from inside any graph node.

    Args:
        data: Optional chunk data.
        timeout: Optional timeout in seconds for the blocking wait. If None, wait indefinitely.
    """

    try:
        context = get_graph_context()
    except RuntimeError as exc:
        raise RuntimeError(
            "interrupt() is only available while a graph is invoked."
        ) from exc

    if not context.is_active:
        raise RuntimeError(
            "interrupt() is only available while an active graph node "
            "is executed."
        )

    run_id = context.run_id
    namespace = context._context_namespace
    assert run_id is not None
    assert namespace is not None

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    block = Block(
        run_id=run_id,
        block_id=uuid4().hex,
        namespace=namespace,
        with_data=data,
        _future=future,
    )
    await event_pipe_writer.post_event(
        event_type=EventType.WORKFLOW,
        event_name=f"graph_{namespace}_interrupted",
        context=block,
    )

    try:
        if timeout is None:
            return await block
        return await asyncio.wait_for(block, timeout)
    except TimeoutError:
        return None
    except asyncio.CancelledError:
        # External ``Block.cancel()`` aborts the owning graph attempt at its
        # last committed snapshot. The CancelledError is then re-raised to
        # stop the interrupted node immediately, so neither its remaining
        # code nor a downstream route can run. Runtime task cancellation is
        # left to the surrounding graph timeout/cancellation machinery.
        current_task = asyncio.current_task()
        if block.cancelled and (
            current_task is None or current_task.cancelling() == 0
        ):
            context.abort()
        raise


def interrupted_hook(
    namespace: str | None = None,
    *,
    exist_ok: bool = True,
) -> Callable[
    [InterruptedHandler],
    InterruptedHandler,
]:
    """Register a callback receiving the :class:`Block` for a namespace.

    The event runtime dispatches :class:`ApixEvent` objects internally. This
    decorator hides that transport detail and gives application callbacks the
    ``Block`` promised by the public API.

    Usage:
        @interrupted_hook(namespace="agent")
        async def on_interrupted(block: Block):
            ...
    """
    event_name = f"graph_{namespace or ''}_interrupted"

    def decorator(func: InterruptedHandler) -> InterruptedHandler:
        @wraps(func)
        async def dispatch_block(event: ApixEvent) -> None:
            block = event.context
            if not isinstance(block, Block):
                raise TypeError(
                    "Interrupted graph events must carry a Block context."
                )
            await func(block)

        apix_event_registry.subscribe(
            event_name,
            exist_ok=exist_ok,
        )(dispatch_block)
        return func

    return decorator
