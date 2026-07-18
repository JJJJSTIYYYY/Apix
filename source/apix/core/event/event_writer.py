import time
from typing import Any

from apix.common.utils.logger import logger
from apix.core.event.base import EventType, ApixEvent
from apix.core.event.event_pipe import EVENT_PIPE
    

class EventPipeWriter:

    async def post_event(
        self,
        *,
        event_type: EventType,
        event_name: str,
        context: Any = None
    ) -> None:
        '''
        Post an event to event pipe.

        Args:
            event_type: EventType enum.
            event_name: Custom event name, the event will be delegated by this name to event handler.
            context: Current running context.
        '''
        
        event = ApixEvent(
            event_type = event_type,
            event_name = event_name,
            context = context,
            timestamp = time.time(),
            accepted=False
        )

        await EVENT_PIPE.put(event)

    async def get_event(self) -> ApixEvent:
        return await EVENT_PIPE.get()
    
    async def clear(self):
        count = 0
        while not EVENT_PIPE.empty():
            await EVENT_PIPE.get()
            count = count + 1

        logger.info(f"Cleaned {count} in event pipe.")
        return count



event_pipe = EventPipeWriter()