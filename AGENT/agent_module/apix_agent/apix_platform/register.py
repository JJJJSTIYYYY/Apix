from apix_agent.commons.logger import logger


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
    logger.success(f"[register_platform] Registered platform: {platform} ")
