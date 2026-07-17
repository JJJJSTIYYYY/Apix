import time
from typing import Any

from apix.common.type.global_type import ApixIdentity
from apix.common.utils.logger import logger
from apix.runtime.core.event.base import EventType, ApixEvent
from apix.runtime.core.event.event_pipe import EVENT_PIPE
    

class EventPipeWriter:

    async def post_event(
        self,
        *,
        target: ApixIdentity = None,
        event_type: EventType,
        event_name: str,
        context: Any = None
    ) -> None:
        '''
        Args:
            target: Event receiver, indicate which user or conversation the event belongs to.
            event_type: EventType enum.
            event_name: Custom event name, the event will be delegated by this name to event handler.
            context: Current running context.
        '''
        
        event = ApixEvent(
            target = target,
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