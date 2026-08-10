from asyncio import Future
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Block:
    run_id: str
    block_id: str
    namespace: str
    with_data: Any

    _future: Future[Any]

    def __await__(self):
        return self._future.__await__()

    def resolve(self, result: Any):
        """Resolve the block with `result`, unblocking the interrupted execution."""
        if self._future is None:
            raise RuntimeError("Cannot resolve a uninitialized block.")

        if self._future.done():
            return

        self._future.set_result(result)

    def cancel(self):
        """Cancel the block and unblocking the interrupted execution."""
        if self._future is None:
            raise RuntimeError("Cannot resolve a uninitialized block.")

        self._future.cancel()