import time
from abc import ABC

from apix_agent.commons.logger import logger
from apix_agent.apix_platform.register import PLATFORM_REGISTRY
from apix_agent.commons.type_def import ApixIdentity, MinimalEnvelopeData, ApixEventEnvelope, PlatformNotRegister


class EventHandler(ABC):

    def _build_envelope(
        self,
        event: str,
        target: ApixIdentity,
        data: MinimalEnvelopeData,
        generation_id: str,
    ) -> ApixEventEnvelope:
        return {
            "event": event,
            "target": target,
            "data": data,
            "generation_id": generation_id,
            "timestamp": time.time(),
        }
    
    async def _send_envelope(
        self,
        target: ApixIdentity,
        envelope: ApixEventEnvelope = None
    ):
        """
        Dispatch envelope to different platform senders.

        - default → websocket
        - extensible via @send_interface
        """

        if not envelope:
            return
        
        try: 
            client_id = target.get("id")
            platform = target.get("platform")
            sender = PLATFORM_REGISTRY.get(platform)

            if not sender:
                raise PlatformNotRegister(platform=platform)
            
            envelope = await self._before_send(envelope)

            await sender.send(client_id, envelope)

            await self._after_send(envelope)

        except PlatformNotRegister as e:
            raise e

        except Exception as e:
            logger.error(f"Error: {e}")


    # Extension hooks
    async def _before_send(
        self,
        envelope: ApixEventEnvelope,
    ) -> ApixEventEnvelope:
        return envelope

    async def _after_send(
        self,
        envelope: ApixEventEnvelope,
    ) -> None:
        pass