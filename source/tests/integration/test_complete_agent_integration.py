"""Complex graph/tool integration tests that simulate a full Agent turn."""

import asyncio
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

import pytest
import pytest_asyncio

from apix.agent.sdk.tool import (
    AutoInjection,
    ToolInjectionContext,
    ToolNode,
    tool,
)
from apix.agent.sdk.utils.message import (
    ApixAiMessage,
    ApixToolMessage,
    ApixUserMessage,
)
from apix.core.event import (
    APIX_EVENT_REGISTRY,
    EVENT_PIPE,
    ApixEvent,
    delete_handler_from_registry,
    get_handler_meta,
    get_unmatched_subscriptions,
    subscribe,
    unsubscribe,
)
from apix.core.event.event_loop import APIX_EVENT_LOOP
from apix.core.graph import (
    AutoMerge,
    Command,
    END,
    GraphManager,
    KeepRef,
    START,
)


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(
    autouse=True,
    scope="module",
    loop_scope="session",
)
async def stop_event_runtime_after_module():
    yield
    await APIX_EVENT_LOOP.stop()
    await EVENT_PIPE.clear()


@dataclass
class AgentMemory:
    """Mutable resource deliberately shared by all node state snapshots."""

    notes: list[str] = field(default_factory=list)
    call_ids: list[str] = field(default_factory=list)


@dataclass
class InMemoryMessageStore:
    """Persistence stand-in that records new messages in write batches."""

    messages: list[Any] = field(default_factory=list)
    message_uids: set[str] = field(default_factory=set)
    batches: list[list[str]] = field(default_factory=list)

    def __add__(self, messages: list[Any]) -> "InMemoryMessageStore":
        """Persist one AutoMerge update without replacing the store object."""
        self.messages.extend(messages)
        self.message_uids.update(
            message.message_uid
            for message in messages
        )
        self.batches.append([message.role for message in messages])
        return self

    def __deepcopy__(self, memo):
        raise AssertionError(
            "AutoMerge + KeepRef message store must not be deep-copied"
        )


class CompleteAgentState(TypedDict, total=False):
    messages: Annotated[list[Any], AutoMerge()]
    audit: Annotated[list[str], AutoMerge()]
    lifecycle: Annotated[list[str], AutoMerge()]
    model_calls: Annotated[int, AutoMerge()]
    context_preparations: Annotated[int, AutoMerge()]
    memory: Annotated[AgentMemory, KeepRef()]
    message_store: Annotated[
        InMemoryMessageStore,
        AutoMerge(),
        KeepRef(),
    ]
    prepared_context: list[Any]
    calculation: int


def _call(tool_name: str, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "tool_name": tool_name,
        "args": args,
    }


class ScriptedBot:
    """Deterministic stand-in for a model provider in an Agent loop."""

    def __init__(self) -> None:
        self.tool_schemas: list[dict[str, Any]] = []
        self.requests: list[list[Any]] = []

    def bind_tools(self, tool_node: ToolNode) -> "ScriptedBot":
        self.tool_schemas = tool_node.get_schemas()
        return self

    async def invoke(self, messages: list[Any]) -> ApixAiMessage:
        self.requests.append(list(messages))
        await asyncio.sleep(0)

        tool_messages = [
            message
            for message in messages
            if isinstance(message, ApixToolMessage)
        ]
        if not tool_messages:
            return ApixAiMessage(
                name="Alice",
                content="",
                finish_reason="tool_calls",
                tool_calls=[
                    _call("lookup_weather", "call-weather", {"city": "Tokyo"}),
                    _call("add", "call-add", {"left": 19, "right": 23}),
                    _call("remember", "call-memory", {"note": "Tokyo is warm"}),
                ],
            )

        outputs = {message.name: message.content for message in tool_messages}
        return ApixAiMessage(
            name="Alice",
            content=(
                f"{outputs['lookup_weather']}; "
                f"sum={outputs['add']}; "
                f"memory={outputs['remember']}"
            ),
            finish_reason="stop",
        )


async def test_full_agent_model_tool_model_loop_with_shared_runtime_state():
    """Prepare, model, persist, tools, persist, and final model work together."""
    remember_started = asyncio.Event()
    completion_order: list[str] = []

    @tool(description="Look up current weather for a city.")
    async def lookup_weather(city: str) -> str:
        await remember_started.wait()
        await asyncio.sleep(0.01)
        completion_order.append("lookup_weather")
        return f"weather:{city}:sunny"

    @tool(description="Add two integers.")
    async def add(left: int, right: int) -> Command:
        await asyncio.sleep(0)
        completion_order.append("add")
        total = left + right
        return Command(
            update={
                "messages": [
                    ApixToolMessage(
                        content=str(total),
                        tool_call_id="runtime-overwrites-this",
                    )
                ],
                "audit": [f"calculated:{left}+{right}"],
                "calculation": total,
            }
        )

    @tool(description="Remember one note for the current Agent run.")
    async def remember(
        note: str,
        runtime: Annotated[ToolInjectionContext, AutoInjection()],
    ) -> str:
        remember_started.set()
        runtime.state["memory"].notes.append(note)
        runtime.state["memory"].call_ids.append(runtime.tool_call_id)
        completion_order.append("remember")
        return "stored"

    tool_node = ToolNode([lookup_weather, add, remember])
    bot = ScriptedBot().bind_tools(tool_node)

    def prepare_context(state: dict[str, Any]) -> Command:
        """Build the exact message snapshot supplied to the next model call."""
        preparation_number = state.get("context_preparations", 0) + 1
        return Command(
            update={
                "prepared_context": list(state["messages"]),
                "context_preparations": 1,
                "lifecycle": [f"prepare_context:{preparation_number}"],
            }
        )

    async def call_model(state: dict[str, Any]) -> Command:
        response = await bot.invoke(state["prepared_context"])
        return Command(
            update={
                "messages": [response],
                "model_calls": 1,
                "lifecycle": ["model"],
            }
        )

    def persist_messages(state: dict[str, Any]) -> Command:
        """Persist only unseen messages and route from the stored message type."""
        store = state["message_store"]
        pending_messages = [
            message
            for message in state["messages"]
            if message.message_uid not in store.message_uids
        ]
        latest = state["messages"][-1]
        if isinstance(latest, ApixAiMessage):
            next_node = tool_node.name if latest.tool_calls else END
        else:
            next_node = "prepare_context"

        return Command(
            update={
                "message_store": pending_messages,
                "lifecycle": [
                    f"persist:{latest.role}:{len(pending_messages)}"
                ]
            },
            goto=next_node,
        )

    graph = (
        GraphManager(CompleteAgentState)
        .add_node(prepare_context)
        .add_node(call_model, "model")
        .add_node(tool_node)
        .add_node(persist_messages)
        .add_edge(START, "prepare_context")
        .add_edge("prepare_context", "model")
        .add_edge("model", "persist_messages")
        .add_edge(tool_node.name, "persist_messages")
        .compile_graph()
    )

    memory = AgentMemory()
    message_store = InMemoryMessageStore()
    user_message = ApixUserMessage(content="Tokyo weather and 19 + 23?")
    initial_state = {
        "messages": [user_message],
        "audit": [],
        "lifecycle": [],
        "model_calls": 0,
        "context_preparations": 0,
        "memory": memory,
        "message_store": message_store,
    }

    result = await asyncio.wait_for(graph.invoke(initial_state), timeout=1)

    assert [schema["function"]["name"] for schema in bot.tool_schemas] == [
        "lookup_weather",
        "add",
        "remember",
    ]
    remember_parameters = bot.tool_schemas[2]["function"]["parameters"]
    assert set(remember_parameters["properties"]) == {"note"}
    assert remember_parameters["required"] == ["note"]

    assert completion_order[-1] == "lookup_weather"
    assert set(completion_order[:2]) == {"add", "remember"}
    assert len(bot.requests) == 2
    assert [len(request) for request in bot.requests] == [1, 5]
    assert isinstance(bot.requests[0][0], ApixUserMessage)
    assert all(
        isinstance(message, ApixToolMessage)
        for message in bot.requests[1][-3:]
    )
    assert result["model_calls"] == 2
    assert result["context_preparations"] == 2
    assert result["calculation"] == 42
    assert result["audit"] == ["calculated:19+23"]
    assert result["lifecycle"] == [
        "prepare_context:1",
        "model",
        "persist:ai:2",
        "persist:tool:3",
        "prepare_context:2",
        "model",
        "persist:ai:1",
    ]

    assert result["memory"] is memory
    assert memory.notes == ["Tokyo is warm"]
    assert memory.call_ids == ["call-memory"]
    assert result["message_store"] is message_store
    assert message_store.batches == [
        ["user", "ai"],
        ["tool", "tool", "tool"],
        ["ai"],
    ]
    assert [message.role for message in message_store.messages] == [
        "user",
        "ai",
        "tool",
        "tool",
        "tool",
        "ai",
    ]
    assert len(message_store.message_uids) == 6

    messages = result["messages"]
    assert messages[0] is not user_message
    assert isinstance(messages[0], ApixUserMessage)
    assert isinstance(messages[1], ApixAiMessage)
    assert [message.name for message in messages[2:5]] == [
        "lookup_weather",
        "add",
        "remember",
    ]
    assert [message.tool_call_id for message in messages[2:5]] == [
        "call-weather",
        "call-add",
        "call-memory",
    ]
    assert all(message.metadata["duration"] >= 0 for message in messages[2:5])
    assert isinstance(messages[-1], ApixAiMessage)
    assert messages[-1].tool_calls == []
    assert messages[-1].content == (
        "weather:Tokyo:sunny; sum=42; memory=stored"
    )

    # Ordinary input was isolated, while the explicitly marked resource was
    # intentionally shared back to its caller.
    assert initial_state["messages"] == [user_message]
    assert initial_state["audit"] == []
    assert initial_state["lifecycle"] == []


async def test_agent_plugins_enrich_context_and_observe_node_events():
    """Plugins can extend an Agent run entirely through public core APIs."""
    prepare_event = "complete_agent.plugin.prepare"
    model_event = "complete_agent.plugin.model"
    persist_event = "complete_agent.plugin.persist"

    @subscribe(model_event, priority=20, exist_ok=False)
    async def add_safety_policy(event: ApixEvent) -> None:
        state = event.context.state
        state["model_input"] += " | safety=enabled"
        state["plugin_trace"].append("safety:model")

    @subscribe(
        "complete_agent.plugin.*",
        priority=10,
        filter_event=[persist_event],
        exist_ok=False,
    )
    async def observe_agent_nodes(event: ApixEvent) -> None:
        event.context.state["plugin_trace"].append(
            f"observe:{event.event_name.rsplit('.', 1)[-1]}"
        )

    def prepare_model_input(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "model_input": f"{state['prompt']} | locale={state['locale']}",
            "agent_trace": [*state["agent_trace"], "prepare"],
        }

    def call_model(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "answer": f"answer({state['model_input']})",
            "agent_trace": [*state["agent_trace"], "model"],
        }

    def persist_answer(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "persisted_answer": state["answer"],
            "agent_trace": [*state["agent_trace"], "persist"],
        }

    graph = (
        GraphManager()
        .add_node(prepare_model_input, prepare_event)
        .add_node(call_model, model_event)
        .add_node(persist_answer, persist_event)
        .add_edge(START, prepare_event)
        .add_edge(prepare_event, model_event)
        .add_edge(model_event, persist_event)
        .compile_graph(using_namespace="complete_agent_plugin_runtime")
    )

    try:
        result = await asyncio.wait_for(
            graph.invoke(
                {
                    "prompt": "Summarize the release",
                    "locale": "en-US",
                    "plugin_trace": [],
                    "agent_trace": [],
                }
            ),
            timeout=1,
        )

        assert result["model_input"] == (
            "Summarize the release | locale=en-US | safety=enabled"
        )
        assert result["answer"] == (
            "answer(Summarize the release | locale=en-US | safety=enabled)"
        )
        assert result["persisted_answer"] == result["answer"]
        assert result["agent_trace"] == ["prepare", "model", "persist"]
        assert result["plugin_trace"] == [
            "observe:prepare",
            "safety:model",
            "observe:model",
        ]
    finally:
        graph.decompose()
        delete_handler_from_registry(add_safety_policy.__name__)
        delete_handler_from_registry(observe_agent_nodes.__name__)


async def test_plugin_diagnostics_and_unsubscribe_follow_public_lifecycle():
    """A plugin author can inspect coverage and disable selected hooks."""
    prepare_event = "complete_agent.extension.prepare"
    model_event = "complete_agent.extension.model"
    unseen_pattern = "complete_agent.extension.never.*"
    calls: list[str] = []

    @subscribe(
        "complete_agent.extension.*",
        unseen_pattern,
        priority=5,
        exist_ok=False,
    )
    async def record_extension_event(event: ApixEvent) -> None:
        calls.append(event.event_name)

    def prepare(state: dict[str, Any]) -> dict[str, Any]:
        return {"prepared": state["prompt"].upper()}

    def model(state: dict[str, Any]) -> dict[str, Any]:
        return {"answer": f"model:{state['prepared']}"}

    graph = (
        GraphManager()
        .add_node(prepare, prepare_event)
        .add_node(model, model_event)
        .add_edge(START, prepare_event)
        .add_edge(prepare_event, model_event)
        .compile_graph(using_namespace="complete_agent_extension_runtime")
    )

    try:
        handler_meta = get_handler_meta(record_extension_event.__name__)
        assert handler_meta is not None
        assert handler_meta["subscribe"] == [
            "complete_agent.extension.*",
            unseen_pattern,
        ]
        assert handler_meta["priority"] == 5
        assert get_unmatched_subscriptions(record_extension_event.__name__) == [
            "complete_agent.extension.*",
            unseen_pattern,
        ]

        first_result = await graph.invoke({"prompt": "hello"})
        assert first_result["answer"] == "model:HELLO"
        assert calls == [prepare_event, model_event]
        assert get_unmatched_subscriptions(record_extension_event.__name__) == [
            unseen_pattern
        ]
        assert {prepare_event, model_event}.issubset(
            APIX_EVENT_REGISTRY.get_registered_events()
        )

        calls.clear()
        unsubscribe(record_extension_event.__name__, [model_event])
        await graph.invoke({"prompt": "second"})
        assert calls == [prepare_event]
        assert get_handler_meta(record_extension_event.__name__)[
            "filter_event"
        ] == [model_event]

        calls.clear()
        unsubscribe(record_extension_event.__name__)
        await graph.invoke({"prompt": "third"})
        assert calls == []
    finally:
        graph.decompose()
        delete_handler_from_registry(record_extension_event.__name__)
