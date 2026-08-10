import asyncio
from collections.abc import Awaitable
from uuid import uuid4

from typing import Any, Callable, Optional

from apix.core.graph.context.manager import get_graph_context
from apix.core.event import EventType, event_pipe_writer, apix_event_registry
from apix.core.graph.interrupter.base import Block


async def interrupt(
    *,
    data: Any = None,
    timeout: Optional[float] = None,
) -> Any:
    """
    Send data and while in graph loop and block the agent graph at the same time.
    Can be called from inside any graph node.

    Args:
        data: Optional chunk data.
        timeout: Optional timeout in seconds for the blocking wait. If None, wait indefinitely.
    """

    block_id = uuid4().hex

    try:
        context = get_graph_context()
    except RuntimeError:
        raise RuntimeError("interrupt() is only available while a graph is invoked.")
    
    run_id = context.run_id
    namespace = context._context_namespace or ""

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    block = Block(
        run_id=run_id,
        block_id=block_id,
        namespace=namespace,
        with_data=data,
        _future=future
    )
    await event_pipe_writer.post_event(
        event_type=EventType.WORKFLOW,
        event_name=f"graph_{namespace}_interrupted",
        context=block,
    )

    try:
        if timeout is not None:
            result = await asyncio.wait_for(block, timeout)
        else:
            result = await block

        return result

    except TimeoutError:
        return None


def interrupted_hook(
    namespace: str | None = None,
) -> Callable[
    [Callable[[Block], Awaitable[None]]],
    Callable[[Block], Awaitable[None]],
]:
    """
    Usage:
        @interrupted_hook(namespace="agent")
        async def on_interrupted(block: :class:`Block`):
            ...
    """
    event_name = f"graph_{namespace or ''}_interrupted"

    return apix_event_registry.subscribe(
        event_name,
        exist_ok=True,
    )