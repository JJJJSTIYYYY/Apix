"""Execute tools concurrently and route their combined output."""

import asyncio
from contextlib import AsyncExitStack
from time import perf_counter
from typing import Any

from apixis.core.graph import BaseNode, Command

from apix.agent.core.tool.base import ToolFunction
from apix.agent.core.tool.tool import Tool, tool
from apix.agent.core.utils.funcs import timer
from apix.agent.core.utils.message import ApixAiMessage, ApixToolMessage, ToolCall
from apix.common.utils.logger import logger


class ToolNode(BaseNode):
    """Run the latest assistant's tools and return one combined command.

    Every result is converted with ``str()``, including Command and message
    objects. Only this node's LLM binding determines the next execution target.
    """

    def __init__(
        self,
        tool_set: Tool | ToolFunction | list[Tool | ToolFunction],
        name: str = "tools",
        messages_key: str = "messages",
        timeout: float | None = None,
        *,
        bind_llm_node: str | BaseNode | None = None,
    ) -> None:
        """Create a tool node with an optional LLM execution target.

        Args:
            tool_set: Tools or functions to register, individually or as a list.
            name: Non-empty node name.
            messages_key: State field containing the message list.
            timeout: Maximum node execution time in seconds.
            bind_llm_node: LLM node name or node object; None ends the branch.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("A tool node requires a name.")
        if not isinstance(messages_key, str) or not messages_key:
            raise ValueError("A tool node requires a message key.")

        self.name = name
        self.messages_key = messages_key
        self.timeout = timeout
        self._tools_by_name: dict[str, Tool] = {}
        self.bind_llm_node(bind_llm_node)

        candidates = tool_set if isinstance(tool_set, list) else [tool_set]
        for candidate in candidates:
            if isinstance(candidate, Tool):
                wrapped_tool = candidate
            elif callable(candidate):
                wrapped_tool = Tool(candidate)
            else:
                raise ValueError(
                    "A tool node requires Tool objects or callable "
                    f"functions, got {type(candidate).__name__}."
                )
            if wrapped_tool.name in self._tools_by_name:
                raise ValueError(
                    f"Tool {wrapped_tool.name!r} is already registered "
                    f"in node {self.name!r}."
                )
            self._tools_by_name[wrapped_tool.name] = wrapped_tool

    @property
    def tool_set(self) -> list[Tool]:
        """Return registered tools in registration order."""
        return list(self._tools_by_name.values())

    def bind_llm_node(self, llm_node: str | BaseNode | None) -> "ToolNode":
        """Bind or replace the next LLM node; None clears the binding."""
        if isinstance(llm_node, BaseNode):
            llm_node = llm_node.name
        if llm_node is not None and (not isinstance(llm_node, str) or not llm_node):
            raise ValueError("An LLM binding requires a non-empty node name or None.")
        self._llm_node_name = llm_node
        return self

    def get_schemas(self, filter_names: set[str] | None = None) -> list[dict[str, Any]]:
        """Return copied OpenAI tool definitions in registration order.

        Args:
            filter_names: Optional tool names to include in the returned schemas.
        """
        return [
            registered_tool.get_schema()
            for registered_tool in self._tools_by_name.values()
            if filter_names is None or registered_tool.name in filter_names
        ]

    def _get_tool_calls(self, state: dict[str, Any]) -> list[ToolCall]:
        """Validate the complete batch before starting any tool."""
        if not isinstance(state, dict):
            raise TypeError("state must be a dictionary.")
        messages = state.get(self.messages_key)
        if messages is None:
            return []
        if not isinstance(messages, list):
            raise ValueError(
                f"`{self.messages_key}` must be a message list, "
                f"got {type(messages).__name__}."
            )
        if not messages or not isinstance(messages[-1], ApixAiMessage):
            return []

        tool_calls = messages[-1].tool_calls
        if tool_calls is None:
            return []
        if not isinstance(tool_calls, list):
            raise TypeError(
                "ApixAiMessage.tool_calls must be a list of valid ToolCall objects."
            )
        for tool_call in tool_calls:
            Tool._validate_tool_call(tool_call)
            if tool_call["tool_name"] not in self._tools_by_name:
                raise ValueError(
                    f"Tool {tool_call['tool_name']!r} is not registered "
                    f"in node {self.name!r}."
                )
        return tool_calls

    async def _execute_tool_call(
        self, state: dict[str, Any], tool_call: ToolCall
    ) -> tuple[Any, float]:
        """Execute one tool and record its elapsed time."""
        with timer(
            name="ToolExecution",
            callback=lambda elapsed: logger.info(
                f"Tool {tool_call['tool_name']} (id={tool_call['call_id']}) "
                f"executed in {elapsed * 1000:.2f} ms"
            ),
        ) as start:
            result = await self._tools_by_name[tool_call["tool_name"]].execute(
                state, tool_call
            )
            return result, perf_counter() - start

    async def execute(self, state: dict[str, Any]) -> Command | list[Command]:
        """Wait for all tools, stringify results, and route once in call order.

        A failed or cancelled call cancels and awaits unfinished siblings.
        No pending tool calls returns an empty command list and ends the branch.
        """
        tool_calls = self._get_tool_calls(state)
        if not tool_calls:
            return []

        # Batch resources must outlive every task, including cancellation cleanup.
        async with AsyncExitStack() as stack:
            for tool_name in dict.fromkeys(call["tool_name"] for call in tool_calls):
                batch_context = getattr(
                    self._tools_by_name[tool_name], "tool_call_batch_context", None
                )
                if batch_context is not None:
                    await stack.enter_async_context(batch_context())
            tasks = [
                asyncio.create_task(
                    self._execute_tool_call(state, call),
                    name=f"tool-{call['tool_name']}-{call['call_id']}",
                )
                for call in tool_calls
            ]
            results = await self._gather_tasks_in_order(tasks)

        messages = [
            ApixToolMessage(
                content=str(result),
                name=call["tool_name"],
                tool_call_id=call["call_id"],
                metadata={"duration": duration},
            )
            for call, (result, duration) in zip(tool_calls, results, strict=True)
        ]
        return Command(update={self.messages_key: messages}, goto=self._llm_node_name)


__all__ = ["Tool", "ToolNode", "tool"]
