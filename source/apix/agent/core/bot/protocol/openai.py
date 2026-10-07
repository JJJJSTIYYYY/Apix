import inspect

from apix.agent.core.bot.protocol.base import BaseProtocol


class OpenAIProtocol(BaseProtocol):
    def __init__(
        self, *, endpoint, api_key, model, api_style, timeout, max_retries, client=None
    ):
        if not api_key:
            raise ValueError("api_key must be supplied explicitly")
        self._owns_client = client is None
        if client is None:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=endpoint,
                timeout=timeout,
                max_retries=max_retries,
            )
        self.client = client
        self.api_style = api_style

    async def _dispatch(self, request):
        create = (
            self.client.responses.create
            if self.api_style == "responses"
            else self.client.chat.completions.create
        )
        parameters = inspect.signature(create).parameters
        if any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ):
            return await create(**request)
        # SDK routing only: the complete JSON request was already built above.
        known = {key: value for key, value in request.items() if key in parameters}
        extensions = {
            key: value for key, value in request.items() if key not in parameters
        }
        if extensions:
            known["extra_body"] = extensions
        return await create(**known)

    async def invoke(self, request):
        return await self._dispatch(request)

    async def stream(self, request):
        response_stream = await self._dispatch(request)
        try:
            async for event in response_stream:
                yield event
        finally:
            close = getattr(response_stream, "close", None) or getattr(
                response_stream, "aclose", None
            )
            if close:
                result = close()
                if inspect.isawaitable(result):
                    await result

    async def aclose(self):
        if self._owns_client:
            await self.client.close()
