from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx


class BaseProtocol(ABC):
    @abstractmethod
    async def invoke(self, request: dict[str, Any]) -> Any: ...

    @abstractmethod
    def stream(self, request: dict[str, Any]) -> AsyncIterator[Any]: ...

    async def aclose(self) -> None:
        pass


class HTTPProtocol(BaseProtocol):
    """JSON/SSE transport shared by protocols without a required SDK."""

    requires_api_key = False

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model: str,
        api_style: str,
        timeout: float,
        max_retries: int,
        client: Any = None,
    ) -> None:
        if self.requires_api_key and not api_key:
            raise ValueError("api_key must be supplied explicitly")
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.api_style = api_style
        self.max_retries = max_retries
        self.timeout = timeout
        self._owns_client = client is None
        self.client = (
            client if client is not None else httpx.AsyncClient(timeout=timeout)
        )

    @abstractmethod
    def route(self, stream: bool) -> tuple[str, dict[str, str]]: ...

    @asynccontextmanager
    async def _response(self, request, *, stream):
        url, headers = self.route(stream)
        for attempt in range(self.max_retries + 1):
            manager = self.client.stream(
                "POST", url, headers=headers, json=request, timeout=self.timeout
            )
            try:
                response = await manager.__aenter__()
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(min(0.5 * 2**attempt, 8))
                continue
            if (
                response.status_code in (408, 409, 429) or response.status_code >= 500
            ) and attempt < self.max_retries:
                await manager.__aexit__(None, None, None)
                await asyncio.sleep(min(0.5 * 2**attempt, 8))
                continue
            try:
                if response.is_error or not stream:
                    await response.aread()
                response.raise_for_status()
                yield response
            finally:
                await manager.__aexit__(None, None, None)
            return

    async def invoke(self, request):
        async with self._response(request, stream=False) as response:
            return response.json()

    async def stream(self, request):
        async with self._response(request, stream=True) as response:
            data = []
            event_name = ""
            async for line in response.aiter_lines():
                if not line:
                    if data:
                        payload = "\n".join(data)
                        if payload == "[DONE]":
                            return
                        event = json.loads(payload)
                        if event_name and isinstance(event, dict):
                            event.setdefault("type", event_name)
                        yield event
                    data, event_name = [], ""
                elif line.startswith("data:"):
                    data.append(line[5:].lstrip(" "))
                elif line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith((":", "id:", "retry:")):
                    continue
                elif line.startswith("{"):
                    # Ollama native chat uses newline-delimited JSON.
                    yield json.loads(line)
            if data:
                payload = "\n".join(data)
                if payload != "[DONE]":
                    event = json.loads(payload)
                    if event_name and isinstance(event, dict):
                        event.setdefault("type", event_name)
                    yield event

    async def aclose(self):
        if self._owns_client:
            await self.client.aclose()
