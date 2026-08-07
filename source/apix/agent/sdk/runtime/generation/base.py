from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar


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
