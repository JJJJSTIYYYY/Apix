import asyncio
from collections.abc import Awaitable
import functools
import inspect
from typing import (
    Annotated,
    Any,
    Callable,
    TypeGuard,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from apix.common.type.exception import InvalidToolArgs
from apix.core.graph import Command, BaseNode
from apix.agent.sdk.tool.base import ToolFunction
from apix.agent.sdk.tool.context import ToolInjectionState, AutoInjection
from apix.agent.sdk.utils.message import ApixAiMessage, ToolCall, ApixToolMessage


class Tool:
    """An executable tool node.

    Tool functions receive arguments from ``ToolCall.args``. A function may
    declare at most one runtime-injected argument:

        injection: Annotated[ToolInjectionState, AutoInjection()]

    The injected argument is excluded from the tool prompt and cannot be
    supplied through ``ToolCall.args``.
    """

    name: str
    func: Callable[..., Awaitable[Any]]
    prompt: str
    describe: str

    def __init__(
        self,
        func: ToolFunction,
        describe: str | None = None,
    ) -> None:
        """Create a tool.

        Args:
            func: Function invoked when this tool is called.
            name: Tool name. Defaults to ``func.__name__``.
            describe: Tool description. Defaults to the function docstring.

        Raises:
            ValueError: If the function or tool name is invalid, or if more
                than one injected parameter is declared.
            TypeError: If an injected parameter uses an unsupported form.
        """
        if func is None or not callable(func):
            raise ValueError("A tool requires a callable function.")

        self.name = getattr(func, "__name__", None)

        if not self.name:
            raise ValueError("A tool requires a non-empty name.")

        self.describe = (
            describe
            if describe is not None
            else inspect.getdoc(func) or ""
        ).strip()

        self._raw_func = func
        self._signature = inspect.signature(func)
        self._type_hints = self._resolve_type_hints(func)

        self._injection_parameter = (
            self._find_injection_parameter()
        )

        self._validate_signature()

        self.prompt = self._build_prompt()
        self.func = self._wrap_func(func)
        functools.update_wrapper(self, func)

    @staticmethod
    def _resolve_type_hints(
        func: ToolFunction,
    ) -> dict[str, Any]:
        """Resolve function annotations while preserving Annotated metadata."""
        try:
            return get_type_hints(
                func,
                include_extras=True,
            )
        except (NameError, TypeError):
            # Forward references may fail to resolve when the referenced type
            # is defined in a local scope. Falling back to inspect.signature
            # still allows already-resolved annotations to work.
            return {}

    def _get_parameter_annotation(
        self,
        parameter: inspect.Parameter,
    ) -> Any:
        """Return the resolved annotation for a parameter."""
        return self._type_hints.get(
            parameter.name,
            parameter.annotation,
        )

    @staticmethod
    def _parse_injection_annotation(
        annotation: Any,
    ) -> type[ToolInjectionState] | None:
        """Return ToolInjectionState when annotation is auto-injected.

        Supported form:

            Annotated[ToolInjectionState, AutoInjection()]
        """
        if get_origin(annotation) is not Annotated:
            return None

        annotation_args = get_args(annotation)
        if not annotation_args:
            return None

        value_type, *metadata = annotation_args

        has_auto_injection = any(
            marker is AutoInjection
            or isinstance(marker, AutoInjection)
            for marker in metadata
        )

        if not has_auto_injection:
            return None

        if value_type is not ToolInjectionState:
            raise TypeError(
                "Tool node only supports ToolInjectionState."f"got {value_type.__name__}"
            )

        return value_type

    def _is_injection_parameter(
        self,
        parameter: inspect.Parameter,
    ) -> bool:
        """Return whether a parameter is runtime-injected."""
        annotation = self._get_parameter_annotation(
            parameter
        )

        return (
            self._parse_injection_annotation(annotation)
            is ToolInjectionState
        )

    def _find_injection_parameter(
        self,
    ) -> inspect.Parameter | None:
        """Find the optional ToolInjectionState parameter.

        Raises:
            ValueError: If more than one injection parameter is declared.
        """
        injection_parameters = [
            parameter
            for parameter in self._signature.parameters.values()
            if self._is_injection_parameter(parameter)
        ]

        if len(injection_parameters) > 1:
            parameter_names = ", ".join(
                parameter.name
                for parameter in injection_parameters
            )

            raise ValueError(
                f"Tool {self.name!r} may declare at most one "
                "ToolInjectionState parameter, "
                f"but found: {parameter_names}."
            )

        if not injection_parameters:
            return None

        parameter = injection_parameters[0]

        if parameter.kind not in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }:
            raise TypeError(
                f"Injected parameter {parameter.name!r} in tool "
                f"{self.name!r} must be a normal or keyword-only "
                "parameter."
            )

        return parameter

    def _validate_signature(self) -> None:
        """Validate that the function can be called from dictionary args."""
        for parameter in self._signature.parameters.values():
            if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
                raise TypeError(
                    f"Tool {self.name!r} contains positional-only "
                    f"parameter {parameter.name!r}. Tool functions must "
                    "accept arguments by keyword because ToolCall.args is "
                    "a dictionary."
                )

    def _public_signature(self) -> inspect.Signature:
        """Return the function signature visible to the model."""
        parameters: list[inspect.Parameter] = []

        for parameter in self._signature.parameters.values():
            if (
                self._injection_parameter is not None
                and parameter.name
                == self._injection_parameter.name
            ):
                continue

            annotation = self._get_parameter_annotation(
                parameter
            )

            parameters.append(
                parameter.replace(annotation=annotation)
            )

        return self._signature.replace(
            parameters=parameters,
            return_annotation=inspect.Signature.empty,
        )

    def _build_prompt(self) -> str:
        """Build a prompt using description and non-injected parameters."""
        signature = self._public_signature()

        lines = [
            f"Tool: {self.name}",
            f"Arguments: {signature}",
        ]

        if self.describe:
            lines.append(f"Description: {self.describe}")

        return "\n".join(lines)

    @staticmethod
    def _validate_tool_call(
        tool_call: ToolCall,
    ) -> None:
        """Validate the basic runtime structure of a tool call."""
        if not isinstance(tool_call, dict):
            raise TypeError(
                "tool_call must be a ToolCall-compatible dictionary."
            )

        required_keys = {
            "call_id",
            "tool_name",
            "args",
        }

        missing_keys = required_keys.difference(tool_call)

        if missing_keys:
            missing = ", ".join(sorted(missing_keys))
            raise ValueError(
                f"ToolCall is missing required fields: {missing}."
            )

        call_id = tool_call["call_id"]
        tool_name = tool_call["tool_name"]
        args = tool_call["args"]

        if not isinstance(call_id, str) or not call_id:
            raise TypeError(
                "ToolCall.call_id must be a non-empty string."
            )

        if not isinstance(tool_name, str) or not tool_name:
            raise TypeError(
                "ToolCall.tool_name must be a non-empty string."
            )

        if args is not None and not isinstance(args, dict):
            raise TypeError(
                "ToolCall.args must be a dictionary or None."
            )

    def _build_arguments(
        self,
        state: dict[str, Any],
        tool_call: ToolCall,
    ) -> dict[str, Any]:
        """Build function keyword arguments for a tool call."""
        tool_call_args = tool_call["args"]

        arguments = (
            {}
            if tool_call_args is None
            else dict(tool_call_args)
        )

        injection_parameter = self._injection_parameter

        if injection_parameter is None:
            return arguments

        injection_name = injection_parameter.name

        if injection_name in arguments:
            raise TypeError(
                f"Argument {injection_name!r} of tool "
                f"{self.name!r} is automatically injected and "
                "must not be supplied through ToolCall.args."
            )

        arguments[injection_name] = ToolInjectionState(
            state=state,
            tool_call=tool_call,
        )

        return arguments

    def _bind_arguments(
        self,
        arguments: dict[str, Any],
    ) -> inspect.BoundArguments:
        """Validate arguments against the original function signature."""
        try:
            bound_arguments = self._signature.bind(
                **arguments
            ) # Cheak required arguments.
        except TypeError as exc:
            raise InvalidToolArgs(
                f"Invalid arguments for tool {self.name!r}: {exc}"
            ) from exc

        # This is not required for invocation, but makes BoundArguments
        # complete and predictable for wrappers or future middleware.
        bound_arguments.apply_defaults()

        return bound_arguments

    def _wrap_func(
        self,
        func: ToolFunction,
    ) -> Callable[..., Awaitable[Any]]:
        """Wrap sync and async tool functions with one async interface.

        The wrapped function accepts already-bound positional and keyword
        arguments and always returns a Command.
        """

        @functools.wraps(func)
        async def wrapped(
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            result = func(*args, **kwargs)

            if inspect.isawaitable(result):
                result = await result

            return result

        return wrapped
        

    async def execute(
        self,
        state: dict[str, Any],
        tool_call: ToolCall,
    ) -> Any:
        """Validate and execute one tool call.

        Args:
            state: Current graph state.
            tool_call: Tool call generated by the model.

        Returns:
            The tool result normalised as a Command.

        Raises:
            ValueError: If the tool call targets another tool.
            TypeError: If arguments do not match the function signature.
        """
        if not isinstance(state, dict):
            raise TypeError("state must be a dictionary.")

        self._validate_tool_call(tool_call)

        called_tool_name = tool_call["tool_name"]

        if called_tool_name != self.name:
            raise ValueError(
                f"ToolCall targets {called_tool_name!r}, "
                f"but this tool is {self.name!r}."
            )

        arguments = self._build_arguments(
            state=state,
            tool_call=tool_call,
        )

        bound_arguments = self._bind_arguments(arguments)

        return await self.func(
            *bound_arguments.args,
            **bound_arguments.kwargs,
        )
    

@overload
def tool(
    func: ToolFunction,
    *,
    describe: str | None = None,
) -> Tool:
    ...


@overload
def tool(
    func: None = None,
    *,
    describe: str | None = None,
) -> Callable[[ToolFunction], Tool]:
    ...


def tool(
    func: ToolFunction | None = None,
    *,
    describe: str | None = None,
) -> Tool | Callable[[ToolFunction], Tool]:
    """Wrap a regular function as a :class:`Tool`.

    Both ``@tool`` and ``@tool(describe="...")`` are supported. The wrapped
    tool retains the original function name and metadata.
    """
    if func is None:
        return lambda wrapped: Tool(
            wrapped,
            describe=describe,
        )

    if not callable(func):
        raise TypeError("tool decorator requires a callable function.")

    return Tool(
        func,
        describe=describe,
    )


class ToolNode(BaseNode):
    """Execute tool calls from the latest assistant message concurrently."""

    name: str
    tool_set: list[Tool]
    message_key: str
    
    def __init__(
        self, 
        tool_set: Tool | list[Tool] | ToolFunction | list[ToolFunction],
        name: str = "tools",
        message_key: str = "messages",
    ) -> None:
        """Create a node.

        Args:
            tool_set: A ToolFunction instance or a list of ToolFunction instances.
            name: The name of the tool node. Must be a non-empty string.

        Raises:
            ValueError: If `tool_set` is not a ToolFunction or a list of ToolFunctions, 
                or if `name` is empty.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("A tool node requires a name.")
        if not isinstance(message_key, str) or not message_key:
            raise ValueError("A tool node requires a message key.")

        candidates = (
            tool_set
            if isinstance(tool_set, list)
            else [tool_set]
        )

        self.name = name
        self.tool_set = []
        self.message_key = message_key
        self._tools_by_name: dict[str, Tool] = {}

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

            self.tool_set.append(wrapped_tool)
            self._tools_by_name[wrapped_tool.name] = wrapped_tool


    @staticmethod
    def _is_tool_call(
        value: Any,
    ) -> TypeGuard[ToolCall]:
        """
        Runtime validation for ToolCall.

        ToolCall is a TypedDict, so it cannot be used with isinstance().
        """
        if not isinstance(value, dict):
            return False

        if not {
            "call_id",
            "tool_name",
            "args",
        }.issubset(value):
            return False

        if (
            not isinstance(value["call_id"], str)
            or not value["call_id"]
        ):
            return False

        if (
            not isinstance(value["tool_name"], str)
            or not value["tool_name"]
        ):
            return False

        args = value["args"]
        if args is not None and not isinstance(args, dict):
            return False

        return True


    @classmethod
    def _is_tool_call_list(
        cls,
        value: Any,
    ) -> TypeGuard[list[ToolCall]]:
        return (
            isinstance(value, list)
            and all(cls._is_tool_call(item) for item in value)
        )


    @staticmethod
    def _make_tool_message(
        content: str,
        tool_call: ToolCall,
    ) -> ApixToolMessage:
        """Create the message corresponding to one completed tool call."""
        return ApixToolMessage(
            content=content,
            name=tool_call["tool_name"],
            tool_call_id=tool_call["call_id"],
        )


    def _normalise_tool_result(
        self,
        result: Any,
        tool_call: ToolCall,
    ) -> Command:
        """Convert one raw tool result into exactly one command."""
        if not self._is_command(result):
            return Command(
                update={
                    self.message_key: [
                        self._make_tool_message(
                            str(result),
                            tool_call,
                        )
                    ]
                }
            )

        command = Command()

        if "update" in result:
            update = dict(result["update"])
            message_update = update.get(self.message_key)

            if isinstance(message_update, str):
                update[self.message_key] = [
                    self._make_tool_message(
                        message_update,
                        tool_call,
                    )
                ]

            command["update"] = update

        if "goto" in result:
            command["goto"] = result["goto"]

        return command


    async def _execute_tool_call(
        self,
        state: dict[str, Any],
        tool_call: ToolCall,
    ) -> Command:
        """Execute and normalise one validated tool call."""
        selected_tool = self._tools_by_name[tool_call["tool_name"]]
        result = await selected_tool.execute(
            state,
            tool_call,
        )
        return self._normalise_tool_result(
            result,
            tool_call,
        )


    async def execute(
        self,
        state: dict[str, Any],
    ) -> list[Command]:
        """Execute all tool calls concurrently and return them in call order."""
        if not isinstance(state, dict):
            raise TypeError("state must be a dictionary.")

        messages = state.get(self.message_key)

        if messages is None:
            return []

        if not isinstance(messages, list):
            raise ValueError(
                f"`{self.message_key}` must be a message list, "
                f"got {type(messages).__name__}."
            )

        if not messages:
            return []

        last_message = messages[-1]

        if not isinstance(last_message, ApixAiMessage):
            return []

        tool_calls = last_message.tool_calls

        if not tool_calls:
            return []

        if not self._is_tool_call_list(tool_calls):
            raise TypeError(
                "ApixAiMessage.tool_calls must be a list of valid ToolCall objects."
            )

        for tool_call in tool_calls:
            if tool_call["tool_name"] not in self._tools_by_name:
                raise ValueError(
                    f"Tool {tool_call['tool_name']!r} is not registered "
                    f"in node {self.name!r}."
                )

        tasks = [
            asyncio.create_task(
                self._execute_tool_call(
                    state,
                    tool_call,
                ),
                name=(
                    f"tool-{tool_call['tool_name']}-"
                    f"{tool_call['call_id']}"
                ),
            )
            for tool_call in tool_calls
        ]

        try:
            return list(await asyncio.gather(*tasks))
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )
            raise
