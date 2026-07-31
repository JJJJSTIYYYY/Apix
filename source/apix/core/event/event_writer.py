import time
from typing import Any
from uuid import uuid4

from apix.common.utils.logger import logger
from apix.core.event.base import EventType, ApixEvent, ChannelName
from apix.core.event.event_pipe import EVENT_PIPE
    

class EventPipeWriter:

    async def post_event(
        self,
        *,
        event_type: EventType,
        event_name: str,
        context: Any = None,
        channel: ChannelName = "builtin",
        recipient: str | None = None,
    ) -> None:
        '''
        Post an event to event pipe.

        Args:
            event_type: EventType enum.
            event_name: Custom event name, the event will be delegated by this name to event handler.
            context: Current running context.
            channel: Target event channel. Local events use ``builtin``.
            recipient: Destination node MQ id when using ``mailtruck``.
        '''
        
        event = ApixEvent(
            event_id="event-"+uuid4().hex,
            event_type = event_type,
            event_name = event_name,
            context = context,
            timestamp = time.time(),
            accepted=False
        )

        await EVENT_PIPE.put(event, channel, recipient=recipient)

    async def get_event(self) -> ApixEvent:
        return await EVENT_PIPE.get()

    def task_done(self) -> None:
        EVENT_PIPE.task_done()
    
    async def clear(self):
        count = 0
        while not EVENT_PIPE.empty():
            await EVENT_PIPE.get()
            EVENT_PIPE.task_done()
            count = count + 1

        logger.info(f"Cleaned {count} in event pipe.")
        return count



event_pipe_writer = EventPipeWriter()
