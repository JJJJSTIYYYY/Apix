from functools import wraps
from typing import Awaitable, Callable, TypeVar, cast

from apix.common.utils.logger import logger


CacheHandler = TypeVar(
    "CacheHandler",
    bound=Callable[..., Awaitable[dict]],
)


def cache_store_handler(handler: CacheHandler) -> CacheHandler:
    """Trace a cache-store call and normalize its unhandled failures."""

    @wraps(handler)
    async def wrapper(*args, **kwargs) -> dict:
        logger.trace()
        try:
            return await handler(*args, **kwargs)
        except Exception as exc:
            logger.exception(
                f"Cache-store handler `{handler.__name__}` failed: {exc}"
            )
            return {
                "success": False,
                "messages": f"fail: {exc}",
            }

    return cast(CacheHandler, wrapper)
