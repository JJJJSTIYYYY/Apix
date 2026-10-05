"""Tests for agent tool wrapping and ToolNode execution."""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
import inspect
import importlib
from pathlib import Path
import typing
from typing import (
    Annotated,
    Any,
    Literal,
    NotRequired,
    Required,
    TypedDict,
)
from uuid import UUID

import pytest
from pydantic import BaseModel

from apix.agent.core.tool import (
    AutoInjection,
    Tool,
    ToolInjectionContext,
    ToolNode,
    tool,
)
from apix.agent.core.utils.message import (
    ApixAiMessage,
    ApixToolMessage,
)
from apix.agent.core.utils.exception import InvalidToolArgsError
from apixis.core.graph import Command, GraphManager

tool_module = importlib.import_module("apix.agent.core.tool.tool")


class TextUnit(Enum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


class MixedUnit(Enum):
    NAME = "named"
    INDEX = 1


class RequestPayload(TypedDict, total=False):
    name: Required[str]
    count: NotRequired[int]


class OptionalPayload(TypedDict, total=False):
    name: str


@dataclass
class Coordinates:
    latitude: float
    label: str = "unknown"


@dataclass
class DefaultsOnly:
    enabled: bool = True


class QueryModel(BaseModel):
    query: str
    limit: int = 10


class InvalidSchemaModel:
    @classmethod
    def model_json_schema(cls):
        return "not a schema"


class UnknownAnnotation:
    pass


class DescriptionMetadata:
    description = "Metadata description."


def _tool_call(
    tool_name: str,
    call_id: str,
    args: dict | None = None,
) -> dict:
    return {
        "call_id": call_id,
        "tool_name": tool_name,
        "args": args,
    }


def _state_with_calls(*calls: dict) -> dict:
    return {
        "messages": [
            ApixAiMessage(tool_calls=list(calls)),
        ]
    }


def _message_from(command: Command) -> ApixToolMessage:
    messages = command.update["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 1
    message = messages[0]
    assert isinstance(message, ApixToolMessage)
    return message


def test_tool_decorator_preserves_function_name_and_metadata():
    """Both decorator forms create named Tool objects."""

    @tool
    def direct(value: int) -> str:
        """Direct tool."""
        return str(value)

    @tool(description="Custom description")
    def configured(value: int) -> str:
        return str(value)

    assert isinstance(direct, Tool)
    assert direct.name == "direct"
    assert direct.__name__ == "direct"
    assert direct.func.__name__ == "direct"
    assert direct.__doc__ == "Direct tool."

    assert isinstance(configured, Tool)
    assert configured.name == "configured"
    assert configured.description == "Custom description"


def test_tool_builds_openai_function_calling_schema():
    """Tool annotations become a native Chat Completions tool definition."""

    @tool(description="Get the weather forecast.")
    def weather(
        location: Annotated[str, "City and country."],
        days: int,
        runtime: Annotated[
            ToolInjectionContext,
            AutoInjection(),
        ],
        units: Literal["celsius", "fahrenheit"] = "celsius",
        options: dict[str, bool] | None = None,
    ) -> str:
        return location

    assert weather.schema == {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get the weather forecast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and country.",
                    },
                    "days": {"type": "integer"},
                    "units": {
                        "enum": ["celsius", "fahrenheit"],
                        "type": "string",
                        "default": "celsius",
                    },
                    "options": {
                        "anyOf": [
                            {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "boolean",
                                },
                            },
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                },
                "required": ["location", "days"],
                "additionalProperties": False,
            },
        },
    }
    assert "runtime" not in (weather.schema["function"]["parameters"]["properties"])
    assert not hasattr(weather, "prompt")


def test_tool_schema_accessors_return_independent_copies_in_order():
    """Callers can safely pass and mutate schemas without changing tools."""

    @tool
    def first(value: str) -> str:
        return value

    @tool
    def second(count: int = 1) -> str:
        return str(count)

    schema = first.get_schema()
    schema["function"]["name"] = "changed"

    assert first.schema["function"]["name"] == "first"
    assert [
        item["function"]["name"] for item in ToolNode([first, second]).get_schemas()
    ] == ["first", "second"]


def test_tool_rejects_variadic_parameters_not_supported_by_json_schema():
    """Function Calling requires explicitly named model arguments."""

    def variadic(*values: str) -> str:
        return ",".join(values)

    with pytest.raises(TypeError, match="variadic parameter"):
        Tool(variadic)


@pytest.mark.asyncio
async def test_tool_node_executes_concurrently_but_returns_call_order():
    """A later tool can finish first without reordering the combined update."""
    second_started = asyncio.Event()
    completion_order = []

    @tool
    async def first(value: str) -> str:
        await second_started.wait()
        await asyncio.sleep(0.01)
        completion_order.append("first")
        return f"first:{value}"

    @tool
    async def second(value: str) -> str:
        second_started.set()
        completion_order.append("second")
        return f"second:{value}"

    node = ToolNode([first, second], bind_llm_node="model")
    command = await asyncio.wait_for(
        node.execute(
            _state_with_calls(
                _tool_call("first", "call-1", {"value": "a"}),
                _tool_call("second", "call-2", {"value": "b"}),
            )
        ),
        timeout=1,
    )

    assert completion_order == ["second", "first"]
    assert isinstance(command, Command)
    assert command.goto == "model"
    assert [m.content for m in command.update["messages"]] == ["first:a", "second:b"]
    assert [m.tool_call_id for m in command.update["messages"]] == ["call-1", "call-2"]


@pytest.mark.asyncio
async def test_plain_dict_result_is_stringified_into_tool_message():
    """A plain dict is normal tool output."""

    def payload() -> dict:
        return {"answer": 42}

    node = ToolNode(payload)
    command = await node.execute(
        _state_with_calls(
            _tool_call("payload", "call-payload"),
        )
    )

    message = _message_from(command)
    assert message.content == "{'answer': 42}"
    assert message.name == "payload"
    assert message.tool_call_id == "call-payload"


@pytest.mark.asyncio
async def test_string_result_creates_tool_message_with_runtime_metadata():
    """A string result becomes one fully attributed tool message."""

    def text() -> str:
        return "finished"

    node = ToolNode(text)
    command = await node.execute(
        _state_with_calls(
            _tool_call("text", "call-text"),
        )
    )

    assert isinstance(command, Command)
    message = _message_from(command)
    assert message.content == "finished"
    assert message.name == "text"
    assert message.tool_call_id == "call-text"
    assert message.metadata["duration"] >= 0
    assert message.extensions["tool_call_id"] == "call-text"


@pytest.mark.asyncio
async def test_tool_message_result_is_stringified_without_mutation():
    """Returned message objects are plain values, with no special treatment."""
    returned_message = ApixToolMessage(
        content="finished",
        name="stale-name",
        metadata={"stale": True},
        tool_call_id="stale-call",
    )
    expected = str(returned_message)

    def message() -> ApixToolMessage:
        return returned_message

    command = await ToolNode(message).execute(
        _state_with_calls(
            _tool_call("message", "call-message"),
        )
    )
    output = _message_from(command)
    assert output is not returned_message
    assert output.content == expected
    assert output.name == "message"
    assert output.tool_call_id == "call-message"
    assert output.metadata["duration"] >= 0
    assert returned_message.name == "stale-name"
    assert returned_message.tool_call_id == "stale-call"
    assert returned_message.metadata == {"stale": True}


@pytest.mark.asyncio
async def test_command_looking_dict_result_is_still_plain_tool_output():
    """A dictionary is plain output, regardless of its field names."""

    def payload() -> dict:
        return {
            "update": {"value": 3},
            "goto": "next",
        }

    node = ToolNode(payload)
    command = await node.execute(
        _state_with_calls(
            _tool_call("payload", "call-payload"),
        )
    )

    assert _message_from(command).content == (
        "{'update': {'value': 3}, 'goto': 'next'}"
    )
    assert command.goto is None


@pytest.mark.asyncio
async def test_command_result_is_text_and_cannot_update_state_or_route():
    """Even a Command result cannot override the ToolNode's bound target."""
    returned = Command(update={"value": 3}, goto="wrong-node")

    @tool
    def update_state() -> Command:
        return returned

    node = ToolNode(update_state, bind_llm_node="model")
    command = await node.execute(
        _state_with_calls(
            _tool_call("update_state", "call-update"),
        )
    )
    assert command.goto == "model"
    assert set(command.update) == {"messages"}
    assert _message_from(command).content == str(returned)
    assert returned.update == {"value": 3}
    assert returned.goto == "wrong-node"


@pytest.mark.asyncio
async def test_invalid_command_shape_is_stringified():
    """A dict with invalid Command field types is ordinary output."""

    def invalid_shape() -> dict:
        return {"update": []}

    node = ToolNode(invalid_shape)
    command = await node.execute(
        _state_with_calls(
            _tool_call("invalid_shape", "call-invalid"),
        )
    )

    assert _message_from(command).content == "{'update': []}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [
        {},
        {"messages": []},
        {"messages": [ApixToolMessage(content="old", tool_call_id="old")]},
        {"messages": [ApixAiMessage()]},
    ],
)
async def test_tool_node_without_pending_calls_returns_empty_command_list(
    state,
):
    """No pending tool call means no per-tool command is produced."""
    node = ToolNode(lambda: "unused")

    assert await node.execute(state) == []


@pytest.mark.asyncio
async def test_tool_node_rejects_unknown_tool_before_execution():
    """Every model-selected tool must be registered on the node."""
    node = ToolNode(lambda: "unused")

    with pytest.raises(ValueError, match="not registered"):
        await node.execute(
            _state_with_calls(
                _tool_call("missing", "call-missing"),
            )
        )


def test_graph_manager_accepts_tool_node_as_base_node():
    """ToolNode is registered directly instead of being wrapped as a callable."""
    node = ToolNode(lambda: "unused")
    manager = GraphManager().add_node(node)

    assert manager._nodes[node.name] is node


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (Any, {}),
        (
            list[str],
            {
                "type": "array",
                "items": {"type": "string"},
            },
        ),
        (
            set[int],
            {
                "type": "array",
                "items": {"type": "integer"},
                "uniqueItems": True,
            },
        ),
        (
            frozenset[bool],
            {
                "type": "array",
                "items": {"type": "boolean"},
                "uniqueItems": True,
            },
        ),
        (
            Sequence[float],
            {
                "type": "array",
                "items": {"type": "number"},
            },
        ),
        (
            tuple[str, ...],
            {
                "type": "array",
                "items": {"type": "string"},
            },
        ),
        (
            tuple[str, int],
            {
                "type": "array",
                "prefixItems": [
                    {"type": "string"},
                    {"type": "integer"},
                ],
                "minItems": 2,
                "maxItems": 2,
            },
        ),
        (typing.Tuple, {"type": "array"}),
        (
            Mapping[str, int],
            {
                "type": "object",
                "additionalProperties": {"type": "integer"},
            },
        ),
        (
            typing.Mapping,
            {
                "type": "object",
                "additionalProperties": True,
            },
        ),
        (
            typing.List,
            {
                "type": "array",
                "items": {},
            },
        ),
        (
            typing.Sequence,
            {
                "type": "array",
                "items": {},
            },
        ),
        (list, {"type": "array"}),
        (tuple, {"type": "array"}),
        (Sequence, {"type": "array"}),
        (
            set,
            {
                "type": "array",
                "uniqueItems": True,
            },
        ),
        (
            frozenset,
            {
                "type": "array",
                "uniqueItems": True,
            },
        ),
        (dict, {"type": "object"}),
        (Mapping, {"type": "object"}),
        (datetime, {"type": "string", "format": "date-time"}),
        (date, {"type": "string", "format": "date"}),
        (time, {"type": "string", "format": "time"}),
        (UUID, {"type": "string", "format": "uuid"}),
        (Path, {"type": "string"}),
        (bytes, {"type": "string"}),
        (bytearray, {"type": "string"}),
        (Decimal, {"type": "number"}),
        (
            TextUnit,
            {
                "enum": ["celsius", "fahrenheit"],
                "type": "string",
            },
        ),
        (
            MixedUnit,
            {
                "enum": ["named", 1],
            },
        ),
        (
            RequestPayload,
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "additionalProperties": False,
                "required": ["name"],
            },
        ),
        (
            OptionalPayload,
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
        (
            Coordinates,
            {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "label": {"type": "string"},
                },
                "additionalProperties": False,
                "required": ["latitude"],
            },
        ),
        (
            DefaultsOnly,
            {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        ),
        (QueryModel, QueryModel.model_json_schema()),
        (InvalidSchemaModel, {}),
        (UnknownAnnotation, {}),
    ],
)
def test_annotation_to_json_schema_supported_types(annotation, expected):
    """Every advertised annotation family has an explicit schema test."""
    assert Tool._annotation_to_json_schema(annotation) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "null"),
        (True, "boolean"),
        (1, "integer"),
        (1.5, "number"),
        ("value", "string"),
        (object(), None),
    ],
)
def test_json_type_for_literal_values(value, expected):
    assert Tool._json_type_for_value(value) == expected


def test_annotated_metadata_object_supplies_parameter_description():
    schema = Tool._annotation_to_json_schema(Annotated[str, DescriptionMetadata()])

    assert schema == {
        "type": "string",
        "description": "Metadata description.",
    }


def test_annotated_without_description_preserves_underlying_schema():
    assert Tool._annotation_to_json_schema(Annotated[int, object()]) == {
        "type": "integer"
    }
    assert Tool._metadata_description((object(),)) is None


def test_heterogeneous_literal_and_recursive_guard_are_unconstrained():
    assert Tool._annotation_to_json_schema(Literal["name", 1]) == {
        "enum": ["name", 1],
    }
    assert (
        Tool._annotation_to_json_schema(
            str,
            seen=frozenset({id(str)}),
        )
        == {}
    )


def test_non_json_default_is_omitted_from_schema():
    sentinel = object()

    def opaque(value: object = sentinel):
        return value

    wrapped = Tool(opaque)
    value_schema = wrapped.schema["function"]["parameters"]["properties"]["value"]

    assert value_schema == {}
    assert Tool._json_default(sentinel) is inspect.Signature.empty


@pytest.mark.parametrize("invalid_func", [None, 1, "not callable"])
def test_tool_rejects_non_callable_values(invalid_func):
    with pytest.raises(ValueError, match="requires a callable"):
        Tool(invalid_func)


def test_tool_rejects_callable_without_a_name():
    class CallableWithoutName:
        def __call__(self):
            return None

    with pytest.raises(ValueError, match="non-empty name"):
        Tool(CallableWithoutName())


def test_unresolved_forward_reference_falls_back_to_unconstrained_schema():
    def unresolved(value: "TypeThatDoesNotExist"):
        return value

    wrapped = Tool(unresolved)

    assert wrapped._type_hints == {}
    assert wrapped.schema["function"]["parameters"]["properties"]["value"] == {}


def test_auto_injection_rejects_unsupported_value_type():
    def invalid(runtime: Annotated[int, AutoInjection()]):
        return runtime

    with pytest.raises(TypeError, match="only supports ToolInjectionContext"):
        Tool(invalid)


def test_parse_injection_handles_malformed_annotated_metadata(monkeypatch):
    """A defensive empty-args branch remains safe for malformed metadata."""
    malformed = object()
    original_get_origin = tool_module.get_origin
    original_get_args = tool_module.get_args

    monkeypatch.setattr(
        tool_module,
        "get_origin",
        lambda annotation: (
            Annotated if annotation is malformed else original_get_origin(annotation)
        ),
    )
    monkeypatch.setattr(
        tool_module,
        "get_args",
        lambda annotation: (
            () if annotation is malformed else original_get_args(annotation)
        ),
    )

    assert Tool._parse_injection_annotation(malformed) is None


def test_tool_rejects_multiple_injected_parameters():
    Injection = Annotated[ToolInjectionContext, AutoInjection]

    def duplicate(first: Injection, second: Injection):
        return first, second

    with pytest.raises(ValueError, match="at most one"):
        Tool(duplicate)


def test_injected_parameter_must_be_keyword_capable():
    Injection = Annotated[ToolInjectionContext, AutoInjection()]

    def invalid(*runtime: Injection):
        return runtime

    with pytest.raises(TypeError, match="normal or keyword-only"):
        Tool(invalid)


def test_tool_rejects_positional_only_parameter():
    def positional(value, /):
        return value

    with pytest.raises(TypeError, match="positional-only"):
        Tool(positional)


def test_tool_decorator_rejects_non_callable_value():
    with pytest.raises(TypeError, match="requires a callable"):
        tool(123)


@pytest.mark.asyncio
async def test_tool_execute_injects_state_and_applies_defaults():
    observed = {}

    @tool
    def inspect_runtime(
        value: str = "default",
        *,
        runtime: Annotated[
            ToolInjectionContext,
            AutoInjection(),
        ],
    ) -> str:
        observed["value"] = value
        observed["state"] = runtime.state
        observed["call"] = runtime.tool_call
        return runtime.tool_call_id

    state = {"value": 3}
    call = _tool_call("inspect_runtime", "call-runtime")
    result = await inspect_runtime.execute(state, call)

    assert result == "call-runtime"
    assert observed == {
        "value": "default",
        "state": state,
        "call": call,
    }

    with pytest.raises(TypeError, match="automatically injected"):
        await inspect_runtime.execute(
            state,
            _tool_call(
                "inspect_runtime",
                "call-invalid-injection",
                {"runtime": "user supplied"},
            ),
        )


@pytest.mark.asyncio
async def test_tool_execute_validates_state_name_and_bound_arguments():
    @tool
    def required(value: str):
        return value

    with pytest.raises(TypeError, match="state must be"):
        await required.execute(
            [],
            _tool_call("required", "call-state", {"value": "ok"}),
        )

    with pytest.raises(ValueError, match="targets 'other'"):
        await required.execute(
            {},
            _tool_call("other", "call-name", {"value": "ok"}),
        )

    with pytest.raises(InvalidToolArgsError, match="Invalid arguments"):
        await required.execute(
            {},
            _tool_call("required", "call-args"),
        )


@pytest.mark.parametrize(
    ("tool_call", "error", "match"),
    [
        ([], TypeError, "compatible dictionary"),
        ({}, ValueError, "missing required fields"),
        (
            {"call_id": "", "tool_name": "tool", "args": {}},
            TypeError,
            "call_id",
        ),
        (
            {"call_id": 1, "tool_name": "tool", "args": {}},
            TypeError,
            "call_id",
        ),
        (
            {"call_id": "id", "tool_name": "", "args": {}},
            TypeError,
            "tool_name",
        ),
        (
            {"call_id": "id", "tool_name": 1, "args": {}},
            TypeError,
            "tool_name",
        ),
        (
            {"call_id": "id", "tool_name": "tool", "args": []},
            TypeError,
            "args",
        ),
    ],
)
def test_validate_tool_call_rejects_invalid_shapes(tool_call, error, match):
    with pytest.raises(error, match=match):
        Tool._validate_tool_call(tool_call)


@pytest.mark.parametrize("name", ["", None, 1])
def test_tool_node_rejects_invalid_name(name):
    with pytest.raises(ValueError, match="requires a name"):
        ToolNode(lambda: None, name=name)


@pytest.mark.parametrize("messages_key", ["", None, 1])
def test_tool_node_rejects_invalid_messages_key(messages_key):
    with pytest.raises(ValueError, match="message key"):
        ToolNode(lambda: None, messages_key=messages_key)


def test_tool_node_rejects_invalid_and_duplicate_tools():
    with pytest.raises(ValueError, match="Tool objects or callable"):
        ToolNode([object()])

    @tool
    def duplicate():
        return None

    with pytest.raises(ValueError, match="already registered"):
        ToolNode([duplicate, duplicate])


@pytest.mark.asyncio
async def test_tool_output_uses_configured_messages_key():
    node = ToolNode(lambda: "finished", messages_key="history", bind_llm_node="model")
    command = await node.execute(
        {
            "history": [
                ApixAiMessage(
                    tool_calls=[
                        _tool_call("<lambda>", "call-history"),
                    ]
                )
            ]
        }
    )
    assert set(command.update) == {"history"}
    assert command.goto == "model"
    message = command.update["history"][0]
    assert isinstance(message, ApixToolMessage)
    assert message.content == "finished"
    assert message.tool_call_id == "call-history"


@pytest.mark.asyncio
async def test_tool_node_execute_rejects_invalid_state_and_messages():
    node = ToolNode(lambda: None)
    with pytest.raises(TypeError, match="state must be"):
        await node.execute([])
    with pytest.raises(ValueError, match="must be a message list"):
        await node.execute({"messages": "invalid"})
    with pytest.raises(ValueError, match="missing required fields"):
        await node.execute({"messages": [ApixAiMessage(tool_calls=[{}])]})


@pytest.mark.asyncio
async def test_tool_node_cancels_sibling_tasks_after_failure():
    blocker_started = asyncio.Event()
    blocker_cancelled = asyncio.Event()
    never_finishes = asyncio.Event()

    @tool
    async def failing() -> str:
        await blocker_started.wait()
        raise RuntimeError("expected failure")

    @tool
    async def blocking() -> str:
        blocker_started.set()
        try:
            await never_finishes.wait()
        except asyncio.CancelledError:
            blocker_cancelled.set()
            raise
        return "unreachable"

    node = ToolNode([failing, blocking])

    with pytest.raises(RuntimeError, match="expected failure"):
        await asyncio.wait_for(
            node.execute(
                _state_with_calls(
                    _tool_call("failing", "call-failing"),
                    _tool_call("blocking", "call-blocking"),
                )
            ),
            timeout=1,
        )

    assert blocker_cancelled.is_set()


@pytest.mark.parametrize("binding", ["", 1, True, [], object()])
def test_tool_node_rejects_invalid_llm_binding(binding):
    with pytest.raises(ValueError, match="LLM binding"):
        ToolNode(lambda: None, bind_llm_node=binding)


@pytest.mark.asyncio
async def test_llm_node_can_be_bound_replaced_and_cleared():
    from apixis.core.graph import Node

    node = ToolNode(lambda: 42)
    state = _state_with_calls(_tool_call("<lambda>", "call-bind"))
    assert (await node.execute(state)).goto is None
    model = Node(lambda state: {}, name="model")
    assert node.bind_llm_node(model) is node
    assert (await node.execute(state)).goto == "model"
    node.bind_llm_node("replacement")
    assert (await node.execute(state)).goto == "replacement"
    node.bind_llm_node(None)
    assert (await node.execute(state)).goto is None
    assert (
        await ToolNode(lambda: None, bind_llm_node=model).execute(state)
    ).goto == "model"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", [None, 0, False, [1, "two"], b"bytes", Command(update=[], goto=1)]
)
async def test_every_tool_result_is_stringified(value):
    def output():
        return value

    command = await ToolNode(output).execute(
        _state_with_calls(
            _tool_call("output", "call-output"),
        )
    )
    assert _message_from(command).content == str(value)
    assert isinstance(_message_from(command).content, str)
    assert command.goto is None


def test_all_tool_import_paths_share_one_class_and_decorator():
    from apix.agent.core.tool.tool_node import Tool as node_tool, tool as node_decorator
    from apix.agent.core.tool.mcp import MCPTool

    assert Tool is tool_module.Tool is node_tool
    assert tool is tool_module.tool is node_decorator
    assert issubclass(MCPTool, Tool)


@pytest.mark.asyncio
async def test_invalid_later_call_prevents_execution_of_entire_batch():
    executed = []

    def valid():
        executed.append(True)
        return "done"

    node = ToolNode(valid)
    with pytest.raises(ValueError, match="missing required fields"):
        await node.execute(_state_with_calls(_tool_call("valid", "valid-call"), {}))
    assert executed == []


@pytest.mark.asyncio
async def test_caller_cancellation_waits_for_all_running_tools():
    started = asyncio.Event()
    cancelled = []

    async def wait():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    node = ToolNode(wait)
    task = asyncio.create_task(
        node.execute(
            _state_with_calls(
                _tool_call("wait", "first"),
                _tool_call("wait", "second"),
            )
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled == [True, True]
