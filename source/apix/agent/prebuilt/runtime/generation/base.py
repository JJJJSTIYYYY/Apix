import asyncio
import time
from dataclasses import dataclass, field
from typing import Literal
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from apix.agent.sdk.utils.message import ApixAiMessageChunk
from apix.common.type import ApixIdentity


@dataclass
class Generation:
    """
    State for a single AI generation.
    """

    generation_id: str
    target: ApixIdentity

    @property
    def user_uid(self):
        return self.target["id"]

    @property
    def conversation_uid(self):
        return self.target["conversation_uid"]

    @property
    def platform(self):
        return self.target["platform"]

    # running / finished / aborted
    status: Literal["running", "finished", "aborted"] = "running"

    cached_tokens: ApixAiMessageChunk = field(default_factory=lambda: ApixAiMessageChunk())
    parent_node_id: str = field(default='-')

    created_at: float = field(default_factory=time.time)

    # Protect cached_tokens concurrent access
    gen_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Wait for status change
    status_condition: asyncio.Condition = field(
        default_factory=asyncio.Condition
    )


_current_generation_id: ContextVar["str | None"] = ContextVar(
    "agent_generation_id",
    default=None,
)


def get_generation_id() -> str:
    """Return the generation ID bound to the agent graph currently being invoked.

    Raises:
        RuntimeError: If called outside an agent graph invocation context.
    """
    generation_id = _current_generation_id.get()
    if generation_id is None:
        raise RuntimeError(
            "get_generation_id() is only available while a agent graph is being invoked."
        )
    return generation_id


@contextmanager
def generation_id_context(generation_id: str) -> Generator[None]:
    """Bind a generation id for the duration of one node execution."""
    token = _current_generation_id.set(generation_id)
    try:
        yield
    finally:
        _current_generation_id.reset(token)