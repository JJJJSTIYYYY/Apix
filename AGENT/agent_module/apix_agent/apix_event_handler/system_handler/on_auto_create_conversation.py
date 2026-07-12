from apix_agent.commons.logger import logger
from apix_agent.apix_event_pipe.common_event.common_event_gateway import (
    ApixEventItem,
    event_registry
)


@event_registry.on_event("auto_create_conversation", time_out=3, push_to_user=True)
async def inform_sync_conversation(event: ApixEventItem):
    """
    event data:
        event: "info",
        target: ApixIdentity,
        event_name: "auto_create_conversation",
        content: {
            "conversation_uid": str,
            "title": str,
            "work_space": str,
            "created_at": str,
        }
        timestamp: float,
        generation_id: None

    event trigger when:
        A conversation is created by APIX.
    """
    logger.debug("Event detail:", event)
    event.accept()
    
