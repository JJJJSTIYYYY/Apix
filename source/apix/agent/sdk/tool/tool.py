from collections.abc import Awaitable, Mapping, Sequence
from copy import deepcopy
from dataclasses import MISSING, fields, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
import functools
import inspect
import json
from pathlib import Path
import types
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    NotRequired,
    Required,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
    overload,
)
from uuid import UUID

from apix.agent.sdk.utils.exception import InvalidToolArgsError
from apix.agent.sdk.tool.base import ToolFunction
from apix.agent.sdk.tool.tool_context import ToolInjectionContext, AutoInjection
from apix.agent.sdk.utils.message import ToolCall


class Tool:
    """An executable tool with an OpenAI Function Calling schema.

    Tool functions receive arguments from ``ToolCall.args``. A function may
    declare at most one runtime-injected argument:

        injection: Annotated[ToolInjectionContext, AutoInjection()]

    The injected argument is excluded from the model-facing schema and cannot be
    supplied through ``ToolCall.args``.
    """

    name: str
    func: Callable[..., Awaitable[Any]]
    schema: dict[str, Any]
    description: str

    def __init__(
        self,
        func: ToolFunction,
        description: str | None = None,
    ) -> None:
        """Create a tool.

        Args:
            func: Function invoked when this tool is called.
            name: Tool name. Defaults to ``func.__name__``.
            description: Tool description. Defaults to the function docstring.

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

        self.description = (
            description
            if description is not None
            else inspect.getdoc(func) or ""
        ).strip()

        self._raw_func = func
        self._signature = inspect.signature(func)
        self._type_hints = self._resolve_type_hints(func)

        self._injection_parameter = (
            self._find_injection_parameter()
        )

        self._validate_signature()

        self.schema = self._build_schema()
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
    ) -> type[ToolInjectionContext] | None:
        """Return ToolInjectionContext when annotation is auto-injected.

        Supported form:

            Annotated[ToolInjectionContext, AutoInjection()]
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

        if value_type is not ToolInjectionContext:
            raise TypeError(
                "Tool node only supports ToolInjectionContext."f"got {value_type.__name__}"
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
            is ToolInjectionContext
        )

    def _find_injection_parameter(
        self,
    ) -> inspect.Parameter | None:
        """Find the optional ToolInjectionContext parameter.

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
                "ToolInjectionContext parameter, "
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
                    "accept arguments by keyword."
                )
            if parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                raise TypeError(
                    f"Tool {self.name!r} contains variadic parameter "
                    f"{parameter.name!r}. OpenAI Function Calling schemas "
                    "require explicitly declared named parameters."
                )

    @staticmethod
    def _json_type_for_value(value: Any) -> str | None:
        """Return the JSON Schema primitive type for a literal value."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        return None

    @staticmethod
    def _metadata_description(metadata: tuple[Any, ...]) -> str | None:
        """Read an optional parameter description from Annotated metadata."""
        for item in metadata:
            if isinstance(item, str) and item.strip():
                return item.strip()

            description = getattr(item, "description", None)
            if isinstance(description, str) and description.strip():
                return description.strip()

        return None

    @classmethod
    def _annotation_to_json_schema(
        cls,
        annotation: Any,
        *,
        seen: frozenset[int] = frozenset(),
    ) -> dict[str, Any]:
        """Convert a Python type annotation to a JSON Schema fragment."""
        if annotation in {
            inspect.Signature.empty,
            Any,
            object,
        }:
            return {}

        annotation_id = id(annotation)
        if annotation_id in seen:
            return {}
        nested_seen = seen | {annotation_id}

        origin = get_origin(annotation)

        if origin is Annotated:
            value_type, *metadata = get_args(annotation)
            schema = cls._annotation_to_json_schema(
                value_type,
                seen=nested_seen,
            )
            description = cls._metadata_description(tuple(metadata))
            if description:
                schema["description"] = description
            return schema

        if origin in {Union, types.UnionType}:
            variants = [
                cls._annotation_to_json_schema(
                    variant,
                    seen=nested_seen,
                )
                for variant in get_args(annotation)
            ]
            return {"anyOf": variants}

        if origin is Literal:
            values = list(get_args(annotation))
            schema: dict[str, Any] = {"enum": values}
            value_types = {
                cls._json_type_for_value(value)
                for value in values
            }
            value_types.discard(None)
            if len(value_types) == 1:
                schema["type"] = value_types.pop()
            return schema

        if origin in {
            list,
            set,
            frozenset,
            Sequence,
        }:
            item_args = get_args(annotation)
            item_annotation = item_args[0] if item_args else Any
            schema = {
                "type": "array",
                "items": cls._annotation_to_json_schema(
                    item_annotation,
                    seen=nested_seen,
                ),
            }
            if origin in {set, frozenset}:
                schema["uniqueItems"] = True
            return schema

        if origin is tuple:
            item_args = get_args(annotation)

            if not item_args:
                return {"type": "array"}

            if (
                len(item_args) == 2
                and item_args[1] is Ellipsis
            ):
                return {
                    "type": "array",
                    "items": cls._annotation_to_json_schema(
                        item_args[0],
                        seen=nested_seen,
                    ),
                }

            return {
                "type": "array",
                "prefixItems": [
                    cls._annotation_to_json_schema(
                        item_annotation,
                        seen=nested_seen,
                    )
                    for item_annotation in item_args
                ],
                "minItems": len(item_args),
                "maxItems": len(item_args),
            }

        if origin in {dict, Mapping}:
            mapping_args = get_args(annotation)
            value_annotation = (
                mapping_args[1]
                if len(mapping_args) == 2
                else Any
            )
            value_schema = cls._annotation_to_json_schema(
                value_annotation,
                seen=nested_seen,
            )
            return {
                "type": "object",
                "additionalProperties": value_schema or True,
            }

        if annotation in {list, tuple, Sequence}:
            return {"type": "array"}

        if annotation in {set, frozenset}:
            return {
                "type": "array",
                "uniqueItems": True,
            }

        if annotation in {dict, Mapping}:
            return {"type": "object"}

        primitive_types = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            type(None): "null",
        }
        if annotation in primitive_types:
            return {"type": primitive_types[annotation]}

        string_formats = {
            datetime: "date-time",
            date: "date",
            time: "time",
            UUID: "uuid",
        }
        if annotation in string_formats:
            return {
                "type": "string",
                "format": string_formats[annotation],
            }

        if annotation in {Path, bytes, bytearray}:
            return {"type": "string"}

        if annotation is Decimal:
            return {"type": "number"}

        if (
            inspect.isclass(annotation)
            and issubclass(annotation, Enum)
        ):
            values = [member.value for member in annotation]
            schema = {"enum": values}
            value_types = {
                cls._json_type_for_value(value)
                for value in values
            }
            value_types.discard(None)
            if len(value_types) == 1:
                schema["type"] = value_types.pop()
            return schema

        if is_typeddict(annotation):
            type_hints = get_type_hints(
                annotation,
                include_extras=True,
            )
            required_keys = set(
                getattr(annotation, "__required_keys__", ())
            )
            properties: dict[str, Any] = {}

            for name, value_type in type_hints.items():
                value_origin = get_origin(value_type)
                if value_origin in {Required, NotRequired}:
                    value_type = get_args(value_type)[0]
                properties[name] = cls._annotation_to_json_schema(
                    value_type,
                    seen=nested_seen,
                )

            schema = {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            }
            if required_keys:
                schema["required"] = [
                    name
                    for name in properties
                    if name in required_keys
                ]
            return schema

        if inspect.isclass(annotation) and is_dataclass(annotation):
            type_hints = get_type_hints(
                annotation,
                include_extras=True,
            )
            properties: dict[str, Any] = {}
            required: list[str] = []

            for data_field in fields(annotation):
                value_type = type_hints.get(
                    data_field.name,
                    data_field.type,
                )
                properties[data_field.name] = (
                    cls._annotation_to_json_schema(
                        value_type,
                        seen=nested_seen,
                    )
                )
                if (
                    data_field.default is MISSING
                    and data_field.default_factory is MISSING
                ):
                    required.append(data_field.name)

            schema = {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            }
            if required:
                schema["required"] = required
            return schema

        model_json_schema = getattr(
            annotation,
            "model_json_schema",
            None,
        )
        if callable(model_json_schema):
            generated_schema = model_json_schema()
            if isinstance(generated_schema, dict):
                return generated_schema

        # An unconstrained JSON value is more accurate than guessing a type
        # for an annotation that JSON Schema cannot represent.
        return {}

    @staticmethod
    def _json_default(value: Any) -> Any:
        """Return a JSON-compatible copy of a Python default value."""
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return inspect.Signature.empty
        return deepcopy(value)

    def _build_parameters_schema(self) -> dict[str, Any]:
        """Build the model-visible JSON Schema for function arguments."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for parameter in self._signature.parameters.values():
            if (
                self._injection_parameter is not None
                and parameter.name
                == self._injection_parameter.name
            ):
                continue

            annotation = self._get_parameter_annotation(parameter)
            parameter_schema = self._annotation_to_json_schema(
                annotation
            )

            if parameter.default is inspect.Signature.empty:
                required.append(parameter.name)
            else:
                default = self._json_default(parameter.default)
                if default is not inspect.Signature.empty:
                    parameter_schema["default"] = default

            properties[parameter.name] = parameter_schema

        parameters: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            parameters["required"] = required

        return parameters

    def _build_schema(self) -> dict[str, Any]:
        """Build an OpenAI Chat Completions function tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._build_parameters_schema(),
            },
        }

    def get_schema(self) -> dict[str, Any]:
        """Return a copy safe to pass in the OpenAI ``tools`` list."""
        return deepcopy(self.schema)

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

        arguments[injection_name] = ToolInjectionContext(
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
            raise InvalidToolArgsError(
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
        arguments and returns the tool's raw result.
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
            The raw tool result.

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
    description: str | None = None,
) -> Tool:
    ...


@overload
def tool(
    func: None = None,
    *,
    description: str | None = None,
) -> Callable[[ToolFunction], Tool]:
    ...


def tool(
    func: ToolFunction | None = None,
    *,
    description: str | None = None,
) -> Tool | Callable[[ToolFunction], Tool]:
    """Wrap a regular function as a :class:`Tool`.

    Both ``@tool`` and ``@tool(description="...")`` are supported. The wrapped
    tool retains the original function name and metadata.
    """
    if func is None:
        return lambda wrapped: Tool(
            wrapped,
            description=description,
        )

    if not callable(func):
        raise TypeError("tool decorator requires a callable function.")

    return Tool(
        func,
        description=description,
    )