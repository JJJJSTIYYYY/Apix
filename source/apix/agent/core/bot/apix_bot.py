"""Application role and tool binding around my-llm-py's Chat interface."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any, Self

from my_llm import MessageStream, ModelProfile, MyLLM, ProviderProfile

from apix.agent.core.tool import Tool, ToolNode
from apix.agent.core.utils.context import RoleSchema, to_prompt
from apix.agent.core.utils.message import ApixAiMessage, ApixMessageBase


class ApixBot:
    """Use my-llm-py profiles and OpenAI Chat messages/tools for every provider.

    Profiles configure model/connection behavior; my-llm-py owns SDK clients,
    protocol conversion, stream assembly and terminal validation.
    """

    def __init__(
        self, *, provider: ProviderProfile, model: ModelProfile,
        role_schema: RoleSchema | None = None,
    ) -> None:
        self.llm = MyLLM(provider=provider, model=model, stdio_protocol="openai_chat")
        self.provider = self.llm.provider
        self.model = self.llm.model
        self.role_schema = None
        self._tool_schemas: list[dict] = []
        if role_schema is not None:
            self.bind_role_schema(role_schema)

    @property
    def name(self) -> str:
        """Return the trimmed role name, or ``"assistant"`` without a role."""
        return self.role_schema["name"].strip() if self.role_schema else "assistant"

    def bind_role_schema(self, role_schema: RoleSchema) -> Self:
        """Replace the assistant role with an isolated copy of a schema.

        Args:
            role_schema: Dictionary with a non-empty string name, a string
                definition, and an optional string or None title.

        Returns:
            This bot, allowing chained configuration calls.

        Raises:
            TypeError: The schema or one of its required fields is invalid.
        """
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
        """Return an independent copy of the currently bound function schemas."""
        return deepcopy(self._tool_schemas)

    @staticmethod
    def _schemas(
        tool_set: Iterable[Tool] | ToolNode, permissions: set[str] | None = None
    ) -> list[dict]:
        """Filter tools and copy validated schemas with unique function names."""
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
        names = [schema["function"]["name"] for schema in schemas]
        if len(names) != len(set(names)):
            raise ValueError("function tool names must be unique")
        return deepcopy(schemas)

    def bind_tools(
        self,
        tool_set: Iterable[Tool] | ToolNode,
        tool_permission_set: set[str] | None = None,
    ) -> Self:
        """Replace the function tools available to subsequent requests.

        Args:
            tool_set: Iterable of Apix Tool objects or a ToolNode supplying
                schemas. An empty iterable clears the current tools.
            tool_permission_set: Allowed tool names. None allows all tools;
                an empty set allows none.

        Returns:
            This bot, allowing chained configuration calls.

        Raises:
            TypeError: tool_set is invalid or contains objects other than Tool.
            ValueError: A schema is invalid or function names are duplicated.
        """
        self._tool_schemas = self._schemas(tool_set, tool_permission_set)
        return self

    def _messages(self, messages: list, system_prompt: list | None) -> list[dict]:
        if not isinstance(messages, list):
            raise TypeError("messages must be a list")
        if system_prompt is not None and not isinstance(system_prompt, list):
            raise TypeError("system_prompt must be a list or None")
        result = list(system_prompt or [])
        if self.role_schema:
            result.append({"role": "system", "content": to_prompt(self.role_schema, "RoleSchema")})
        result.extend(messages)
        chat_messages = []
        for message in result:
            if isinstance(message, ApixMessageBase):
                chat_messages.append(message.to_chat())
            elif isinstance(message, Mapping):
                chat_messages.append({
                    key: deepcopy(value) for key, value in message.items()
                    if key not in {"message_uid", "metadata", "extensions"}
                })
            else:
                raise TypeError("messages must contain complete messages or Chat dictionaries")
        return chat_messages

    async def invoke(
        self, messages: list, system_prompt: list | None = None,
        *, tools: Iterable[Tool] | ToolNode | None = None, **parameters: Any,
    ) -> ApixAiMessage:
        """Generate a complete Chat assistant message without executing tools.

        ``parameters`` are my-llm-py generate options, including reasoning,
        max_tokens and extra_body. Provider-specific parameters belong in profiles.
        """
        response = await self.llm.generate(
            messages=self._messages(messages, system_prompt),
            tools=self.tool_schemas if tools is None else self._schemas(tools),
            stream=False, **parameters,
        )
        return ApixAiMessage.from_chat(response)

    async def stream(
        self, messages: list, system_prompt: list | None = None,
        *, tools: Iterable[Tool] | ToolNode | None = None, **parameters: Any,
    ) -> MessageStream:
        """Return the library stream: use async with, then read stream.result.

        Events and result are standard OpenAI Chat dictionaries. The library
        closes requests on success, early exit, cancellation and failure.
        """
        return await self.llm.generate(
            messages=self._messages(messages, system_prompt),
            tools=self.tool_schemas if tools is None else self._schemas(tools),
            stream=True, **parameters,
        )
