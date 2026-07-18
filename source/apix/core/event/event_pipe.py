import asyncio

from apix.config.base_config import EVENT_PIPE_MAX_LEN


EVENT_PIPE = asyncio.Queue(maxsize=EVENT_PIPE_MAX_LEN)