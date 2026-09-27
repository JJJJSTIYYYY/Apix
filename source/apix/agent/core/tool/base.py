from collections.abc import Awaitable
from typing import Any, Callable, TypedDict


ToolFunction = Callable[..., Any] | Callable[..., Awaitable[Any]]
"""A synchronous or asynchronous callable that receives graph state and tool args."""