import asyncio
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

from apix_agent.apix_platform.platform.platform_base import PlatformBase
from apix_agent.commons.logger import logger
from apix_agent.commons.type_def import ApixEventEnvelope


@dataclass
class WebhookContext:
    webhook_url: str
    client_id: str
    headers: dict | None = None


class WebhookPlatform(PlatformBase):

    def __init__(self, platform: str):
        super().__init__(platform)

        self._started = False
        self._webhooks: Dict[str, WebhookContext] = {}

        self._http_client: Optional[httpx.AsyncClient] = None

    # lifecycle
    async def start(self):
        if self._started:
            return

        self._started = True
        self._http_client = httpx.AsyncClient()

    async def stop(self):
        self._started = False

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # webhook management
    async def register(
        self,
        client_id: str,
        webhook_url: str,
        headers: dict | None = None,
    ):
        self._webhooks[client_id] = WebhookContext(
            webhook_url=webhook_url,
            client_id=client_id,
            headers=headers,
        )

    async def unregister(self, client_id: str):
        self._webhooks.pop(client_id, None)

    def _get_ctx(self, client_id: str) -> WebhookContext:
        ctx = self._webhooks.get(client_id)

        if not ctx:
            raise RuntimeError(
                f"Webhook not registered, client id: {client_id}"
            )

        return ctx

    # interface
    async def send(
        self,
        client_id: str,
        envelope: ApixEventEnvelope,
    ):
        if not self._http_client:
            raise RuntimeError(
                f"{self.__class__.__name__} not started"
            )

        ctx = self._webhooks.get(client_id)

        if not ctx:
            return

        payload = self._open_envelope(envelope)

        try:
            await self._http_client.post(
                ctx.webhook_url,
                json=payload,
                headers=ctx.headers,
            )
        except Exception as e:
            logger.exception(f"Webhook send failed, client_id={client_id}: {e}")