from collections.abc import Awaitable, Callable
from typing import Any

ToolFunction = Callable[..., Any] | Callable[..., Awaitable[Any]]
"""A sync or async callable receiving model arguments and optional injection."""
