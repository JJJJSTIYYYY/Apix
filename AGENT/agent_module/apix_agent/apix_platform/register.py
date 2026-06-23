import asyncio

from apix_agent.commons.logger import logger
from apix_agent.apix_event_pipe.common_event.agent_event_writer import event_pipe, AgentCommonEvent


PLATFORM_REGISTRY = {}


def register_platform(instance):
    """
    Register a platform instance.

    instance must have:
        - platform: str
        - async def send(id, envelope)
    """
    platform = getattr(instance, "platform", None)

    if not platform:
        raise ValueError("Platform instance must have 'platform' attribute")

    if platform in PLATFORM_REGISTRY:
        raise RuntimeError(f"Platform already registered: {platform}")

    PLATFORM_REGISTRY[platform] = instance

    asyncio.run(event_pipe.post_event(
        event=AgentCommonEvent.INFO,
        data={
            "event_name": 'on_platform_registered',
            "content": {
                "platform_name": platform
            }
        }
    ))
    logger.success(f"Registered platform: {platform} ")
