import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional

from fastapi import WebSocket

from apix_agent.apix_platform.platform.platform_base import PlatformBase
from apix_agent.apix_agent_core.generation_manager import GenerationManager
from apix_agent.commons.type_def import ApixEventEnvelope
from apix_agent.commons.logger import logger


# User Context
@dataclass
class UserSocketContext:
    websocket: WebSocket
    client_id: str

    # Message queue for this client.
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=1024))

    connected: bool = True
    # Background sender task for this client.
    sender_task: Optional[asyncio.Task] = None

    ctx_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class WebsocketPlatform(PlatformBase):

    def __init__(self, platform: str, gen_mgr: GenerationManager):
        super().__init__(platform)

        self._connections: Dict[str, UserSocketContext] = {}
        self._started: bool = False
        self.gen_mgr = gen_mgr

    # lifecycle
    async def start(self):
        if self._started:
            return

        self._started = True

        for ctx in self._connections.values():
            if ctx.sender_task is None or ctx.sender_task.done():
                ctx.sender_task = asyncio.create_task(self._sender_loop(ctx))

    async def stop(self):
        self._started = False

        tasks = []
        for ctx in self._connections.values():
            if ctx.sender_task:
                ctx.sender_task.cancel()
                tasks.append(ctx.sender_task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        for ctx in self._connections.values():
            ctx.sender_task = None

    # connection management
    async def register(self, websocket: WebSocket, client_id: str):
        old_ctx = self._connections.get(client_id)

        if old_ctx:
            old_ctx.websocket = websocket
            old_ctx.connected = True

            if old_ctx.sender_task:
                old_ctx.sender_task.cancel()
                await asyncio.gather(old_ctx.sender_task, return_exceptions=True)

            old_ctx.sender_task = asyncio.create_task(self._sender_loop(old_ctx))
            return

        ctx = UserSocketContext(websocket=websocket, client_id=client_id)
        self._connections[client_id] = ctx

        if self._started:
            ctx.sender_task = asyncio.create_task(self._sender_loop(ctx))

    async def unregister(self, client_id: str):
        ctx = self._connections.get(client_id)
        if not ctx:
            return

        ctx.connected = False

        if ctx.sender_task:
            ctx.sender_task.cancel()
            await asyncio.gather(ctx.sender_task, return_exceptions=True)

    def _get_ctx(self, client_id: str) -> UserSocketContext:
        ctx = self._connections.get(client_id)
        if not ctx:
            raise RuntimeError(f"WebSocket not registered, client id: {client_id}")
        return ctx

    # sender loop
    async def _sender_loop(self, ctx: UserSocketContext):
        try:
            while True:
                envelope: ApixEventEnvelope = await ctx.queue.get()
                data = self._open_envelope(envelope)

                try:
                    await ctx.websocket.send_json(data)
                except Exception:
                    logger.warning("Websocket send failed - disconnected")
                    ctx.connected = False
                    break

        except asyncio.CancelledError:
            ctx.connected = False
            logger.info(f"Send loop cancelled for client {ctx.client_id}")

    # interface
    async def send(self, client_id: str, envelope: ApixEventEnvelope):
        """
        PlatformBase override

        Directly enqueue event to websocket queue.
        """
        await self.enqueue_event(envelope)


    async def enqueue_event(self, envelope: ApixEventEnvelope):
        target = envelope.get("target") or {}
        client_id = target.get("id")

        if not client_id:
            return

        ctx = self._connections.get(client_id)
        if not ctx:
            return

        await ctx.queue.put(envelope)