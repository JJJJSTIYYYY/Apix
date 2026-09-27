"""Isolate application graphs and asynchronous work through runtime APIs."""

import asyncio

import pytest_asyncio

from apixis.core.event import aget_event_loop, aget_event_pipe
from apixis.core.graph import NodeGraph
from apix.common.utils.logger import Logger


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def cleanup_event_runtime(monkeypatch):
    """Retire test graphs and cancel test-owned tasks without private registries."""
    graphs = []
    original_init = NodeGraph.__init__

    def track_graph(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        graphs.append(self)

    monkeypatch.setattr(NodeGraph, "__init__", track_graph)
    baseline = asyncio.all_tasks()
    pipe = await aget_event_pipe()
    event_loop = await aget_event_loop()
    try:
        yield
    finally:
        for graph in reversed(graphs):
            graph.decompose(force=True)
        tasks = asyncio.all_tasks() - baseline - {asyncio.current_task()}
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await pipe.stop()
        await event_loop.stop()
        await pipe.clear()
        await Logger.stop()
