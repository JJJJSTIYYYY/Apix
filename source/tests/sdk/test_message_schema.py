import asyncio
from unittest.mock import AsyncMock

from apix.agent.sdk.adapter.store import store_adapter as store_adapter_module
from apix.agent.sdk.adapter.context.context_adapter import AIContextAdapter
from apix.agent.sdk.adapter.store.store_adapter import AIStoreAdapter
from apix.agent.sdk.utils.funcs import (
    convert_generation_id_to_message_node_id,
)
from apix.agent.sdk.utils.message import ApixAiMessage, ApixToolMessage


def test_message_object_keeps_only_application_owned_fields():
    message = ApixAiMessage(
        message_uid="message-1",
        name="assistant",
        content="answer",
        metadata={"model": "gpt-test", "usage": {"input_tokens": 2}},
        extensions={
            "reasoning": "because",
            "tool_calls": [
                {
                    "call_id": "call-1",
                    "tool_name": "search",
                    "args": {"query": "apix"},
                }
            ],
            "uploaded_files": ["brief.pdf"],
        },
    )

    assert message.reasoning == "because"
    assert message.tool_calls[0]["call_id"] == "call-1"
    assert message.uploaded_files == ["brief.pdf"]
    assert not hasattr(message, "id")
    assert not hasattr(message, "timestamp")
    assert not hasattr(message, "info")
    assert not hasattr(message, "extra")


def test_extension_properties_update_the_underlying_dictionary():
    message = ApixToolMessage(
        message_uid="message-2",
        name="search",
        content="result",
        tool_call_id="call-1",
    )

    message.active_file = "notes.md"
    message.referenced_message = {"role": "user", "content": "find this"}
    message.task = {"type": "automated_task", "prompt": "summarize"}
    message.todo_list = [{"content": "read", "status": "pending"}]
    message.system_instruction = ["cite sources"]

    assert message.extensions == {
        "tool_call_id": "call-1",
        "active_file": "notes.md",
        "referenced_message": {"role": "user", "content": "find this"},
        "task": {"type": "automated_task", "prompt": "summarize"},
        "todo_list": [{"content": "read", "status": "pending"}],
        "system_instruction": ["cite sources"],
    }


def test_message_storage_conversion_uses_the_new_schema():
    adapter = AIContextAdapter()
    generation_id = "12345678-1234-1234-1234-123456789abc"
    message = ApixAiMessage(
        message_uid="message-3",
        name="assistant",
        content="answer",
        metadata={"provider": "openai"},
        reasoning="internal",
    )

    stored = adapter.convert_to_dict_message(
        message,
        generation_id,
        parent_id="parent-node",
    )

    assert stored == {
        "message_uid": "message-3",
        "generation_id": generation_id,
        "role": "ai",
        "name": "assistant",
        "content": "answer",
        "node_id": convert_generation_id_to_message_node_id(
            generation_id,
            "ai",
        ),
        "parent_id": "parent-node",
        "metadata": {"provider": "openai"},
        "extensions": {"reasoning": "internal"},
    }
    assert {"id", "timestamp", "think", "extra", "info"}.isdisjoint(stored)


def test_database_row_conversion_ignores_database_generated_timestamp():
    adapter = AIContextAdapter()
    messages, todo = adapter.convert_to_apix_messages(
        [
            {
                "message_uid": "message-4",
                "role": "tool",
                "name": "search",
                "content": "result",
                "metadata": '{"duration": 0.5}',
                "extensions": '{"tool_call_id": "call-4"}',
                "timestamp": "2026-07-28T00:00:00",
            }
        ]
    )

    assert todo is None
    assert len(messages) == 1
    assert messages[0].message_uid == "message-4"
    assert messages[0].metadata == {"duration": 0.5}
    assert messages[0].tool_call_id == "call-4"
    assert not hasattr(messages[0], "timestamp")


def test_store_adapter_sends_the_canonical_message_payload():
    query_store = AsyncMock(return_value="success")
    original_query_store = store_adapter_module.query_store
    store_adapter_module.query_store = query_store
    try:
        message = ApixAiMessage(
            message_uid="message-5",
            content="answer",
            reasoning="because",
        )
        asyncio.run(
            AIStoreAdapter().append_to_store(
                message,
                {
                    "id": "user-1",
                    "platform": "web",
                    "conversation_uid": "conversation-1",
                },
                "12345678-1234-1234-1234-123456789abc",
            )
        )
    finally:
        store_adapter_module.query_store = original_query_store

    payload = query_store.await_args.kwargs["payload"]
    assert query_store.await_args.kwargs["action"] == "append_message"
    assert payload["messages"]["message_uid"] == "message-5"
    assert payload["messages"]["extensions"] == {"reasoning": "because"}
    assert {"id", "timestamp", "think", "extra", "info"}.isdisjoint(
        payload["messages"]
    )
