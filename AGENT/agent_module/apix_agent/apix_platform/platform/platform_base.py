from abc import ABC, abstractmethod
from typing import Any

from apix_agent.commons.type_def import ApixEntryDataSchema, ApixEventEnvelope


class PlatformBase(ABC):

    def __init__(self, platform: str):
        self.platform = platform

    @abstractmethod
    async def send(self, id: str, envelope: ApixEventEnvelope):
        """
        Send envelope to client.
        """
        pass

    @abstractmethod
    def trans_payload(self, raw_data: Any) -> ApixEntryDataSchema:
        """
        Translate data package to ApixEntryDataSchema.
        """
        pass

    @abstractmethod
    def _open_envelope(self, envelope: ApixEventEnvelope) -> dict:
        pass