from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Mapping
from copy import deepcopy
from dataclasses import replace
from time import perf_counter
from typing import Any, Self

from apix.agent.core.bot.base import ProviderResponseError
from apix.agent.core.bot.codec import CODECS
from apix.agent.core.bot.codec.base import StreamState, function_schemas
from apix.agent.core.bot.profile import (
    CustomProfile,
    InvocationPolicy,
    ModelProfile,
    ProviderProfile,
)
from apix.agent.core.bot.profile.registry import REGISTRY, ProfileRegistry
from apix.agent.core.bot.protocol import PROTOCOLS, BaseProtocol
from apix.agent.core.bot.providers import register_builtins
from apix.agent.core.bot.request import build_request
from apix.agent.core.tool import Tool, ToolNode
from apix.agent.core.utils.context import RoleSchema, to_prompt
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixAiMessageChunk,
    ApixMessageBase,
    ApixSystemMessage,
)
from apix.config.base_config import LLM_MAX_RETRY, LLM_TIMEOUT

register_builtins(REGISTRY)


class BaseBot:
    """Agent-facing inference API. Context and tool execution belong to Apix."""

    provider = "custom"

    def __init__(
        self,
        *,
        model: str,
        provider: str | ProviderProfile | None = None,
        endpoint: str | None = None,
        api_key: str = "",
        model_profile: ModelProfile | None = None,
        custom_profile: CustomProfile | None = None,
        policy: InvocationPolicy | None = None,
        registry: ProfileRegistry | None = None,
        role_schema: RoleSchema | None = None,
        client: Any = None,
        protocol: BaseProtocol | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not isinstance(api_key, str):
            raise TypeError("api_key must be a string")
        if endpoint is not None and (
            not isinstance(endpoint, str) or not endpoint.strip()
        ):
            raise ValueError("endpoint must be a non-empty string")
        if custom_profile is not None and not isinstance(custom_profile, CustomProfile):
            raise TypeError("custom_profile must be a CustomProfile")
        if model_profile is not None and not isinstance(model_profile, ModelProfile):
            raise TypeError("model_profile must be a ModelProfile")
        if policy is not None and not isinstance(policy, InvocationPolicy):
            raise TypeError("policy must be an InvocationPolicy")
        self.model = model.strip()
        registry = registry or REGISTRY
        provider = self.provider if provider is None else provider
        custom = deepcopy(custom_profile or CustomProfile())
        if endpoint is not None:
            custom = replace(custom, endpoint=endpoint)
        if model_profile is not None:
            custom = replace(custom, model_profile=model_profile)
        if provider == "custom":
            if custom.endpoint is None:
                raise ValueError("endpoint must be supplied for a custom provider")
            provider = ProviderProfile("custom", endpoint=custom.endpoint)
        resolved = registry.resolve(provider, self.model, custom)
        self.provider_profile = resolved.provider
        self.model_profile = resolved.model
        self.provider = self.provider_profile.name
        self.endpoint = self.provider_profile.endpoint.rstrip("/")
        self.api_key = api_key
        self.policy = deepcopy(policy or InvocationPolicy())
        self._codec = CODECS[self.model_profile.api_style](self.model_profile)
        self.role_schema = None
        self._tool_schemas: list[dict] = []
        if role_schema is not None:
            self.bind_role_schema(role_schema)
        self._protocol = (
            protocol
            if protocol is not None
            else PROTOCOLS[self.provider_profile.protocol](
                endpoint=self.endpoint,
                api_key=api_key,
                model=self.model,
                api_style=self.model_profile.api_style,
                timeout=self.policy.timeout
                if self.policy.timeout is not None
                else LLM_TIMEOUT,
                max_retries=self.policy.max_retries
                if self.policy.max_retries is not None
                else LLM_MAX_RETRY,
                client=client,
            )
        )

    @property
    def name(self) -> str:
        return self.role_schema["name"].strip() if self.role_schema else "assistant"

    def bind_role_schema(self, role_schema: RoleSchema) -> Self:
        if (
            not isinstance(role_schema, dict)
            or not isinstance(role_schema.get("name"), str)
            or not role_schema["name"].strip()
            or not isinstance(role_schema.get("definition"), str)
            or role_schema.get("title") is not None
            and not isinstance(role_schema["title"], str)
        ):
            raise TypeError("role_schema must be a RoleSchema object")
        self.role_schema = deepcopy(role_schema)
        return self

    @property
    def tool_schemas(self) -> list[dict]:
        return deepcopy(self._tool_schemas)

    @staticmethod
    def _schemas(
        tool_set: Iterable[Tool] | ToolNode, permissions: set[str] | None = None
    ) -> list[dict]:
        if isinstance(tool_set, ToolNode):
            schemas = tool_set.get_schemas(filter_names=permissions)
        else:
            if isinstance(tool_set, (str, bytes, Mapping)):
                raise TypeError(
                    "tool_set must be an iterable of Tool objects or ToolNode"
                )
            try:
                tools = list(tool_set)
            except TypeError as exc:
                raise TypeError(
                    "tool_set must be an iterable of Tool objects or ToolNode"
                ) from exc
            if any(not isinstance(tool, Tool) for tool in tools):
                raise TypeError("tool_set must contain only Tool objects")
            schemas = [
                tool.get_schema()
                for tool in tools
                if permissions is None or tool.name in permissions
            ]
        functions = function_schemas(schemas)
        names = [function["name"] for function in functions]
        if len(names) != len(set(names)):
            raise ValueError("function tool names must be unique")
        return deepcopy(schemas)

    def bind_tools(
        self,
        tool_set: Iterable[Tool] | ToolNode,
        tool_permission_set: set[str] | None = None,
    ) -> Self:
        self._tool_schemas = self._schemas(tool_set, tool_permission_set)
        return self

    def _ordered_messages(self, messages, system_prompt=None) -> list[ApixMessageBase]:
        if not isinstance(messages, list):
            raise TypeError("messages must be a list")
        if system_prompt is not None and not isinstance(system_prompt, list):
            raise TypeError("system_prompt must be a list or None")
        result = list(system_prompt or [])
        if self.role_schema:
            result.append(
                ApixSystemMessage(content=to_prompt(self.role_schema, "RoleSchema"))
            )
        result.extend(messages)
        return result

    def build_request(
        self,
        messages: list[ApixMessageBase],
        system_prompt=None,
        *,
        tools=None,
        reasoning: bool | None = None,
        reasoning_effort: str | None = None,
        tool_choice: str | None = None,
        parallel_tool_calls: bool | None = None,
        request_options: Mapping | None = None,
        extra_body: Mapping | None = None,
        stream: bool = False,
    ) -> dict:
        schemas = self.tool_schemas if tools is None else self._schemas(tools)
        return build_request(
            model=self.model,
            profile=self.model_profile,
            codec=self._codec,
            messages=self._ordered_messages(messages, system_prompt),
            tools=schemas,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            policy=self.policy,
            request_options=request_options,
            extra_body=extra_body,
            stream=stream,
        )

    def convert_message_for_api(self, message: ApixMessageBase):
        """Compatibility helper; agent code should pass messages to invoke/stream."""
        return self._codec.encode_message(message)

    def _context(self, duration=None) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "name": self.name,
            "duration": duration,
        }

    def convert_message_to_apix(
        self, response, *, stream=False, message_uid=None, duration=None
    ):
        if stream:
            state = StreamState()
            if message_uid:
                state.message_uid = message_uid
            return self._codec.decode_stream(response, state, **self._context(duration))
        return self._codec.decode_response(response, **self._context(duration))

    async def invoke(
        self,
        messages: list[ApixMessageBase],
        system_prompt=None,
        reasoning: bool | None = None,
        reasoning_effort: str | None = None,
        extra_body: Mapping | None = None,
        *,
        tools=None,
        tool_choice: str | None = None,
        parallel_tool_calls: bool | None = None,
        request_options: Mapping | None = None,
    ) -> ApixAiMessage:
        started = perf_counter()
        request = self.build_request(
            messages,
            system_prompt,
            tools=tools,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            request_options=request_options,
        )
        response = await self._protocol.invoke(request)
        return self._codec.decode_response(
            response, **self._context(perf_counter() - started)
        )

    async def stream(
        self,
        messages: list[ApixMessageBase],
        system_prompt=None,
        reasoning: bool | None = None,
        reasoning_effort: str | None = None,
        extra_body: Mapping | None = None,
        *,
        tools=None,
        tool_choice: str | None = None,
        parallel_tool_calls: bool | None = None,
        request_options: Mapping | None = None,
    ) -> AsyncIterator[ApixAiMessageChunk]:
        started = perf_counter()
        request = self.build_request(
            messages,
            system_prompt,
            tools=tools,
            reasoning=reasoning,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            request_options=request_options,
            stream=True,
        )
        state = StreamState()
        source = self._protocol.stream(request)
        try:
            async for event in source:
                chunk = self._codec.decode_stream(
                    event, state, **self._context(perf_counter() - started)
                )
                if (
                    chunk.has_delta
                    or chunk.is_finished
                    or chunk.extensions
                    or "usage" in chunk.metadata
                ):
                    yield chunk
            if not state.finished:
                raise ProviderResponseError(
                    "provider stream ended without a completion event"
                )
        finally:
            close = getattr(source, "aclose", None)
            if close:
                await close()

    async def aclose(self) -> None:
        await self._protocol.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()


Bot = BaseBot
