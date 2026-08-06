from asyncio import Future
from typing import Any, TypedDict

from apix.core.graph.stream import StreamWriter


class GraphContext(TypedDict):
    """Graph context of graph runs."""

    run_id: str
    state: dict
    steps: int
    completion: Future[Any]
    stream_writer: StreamWriter