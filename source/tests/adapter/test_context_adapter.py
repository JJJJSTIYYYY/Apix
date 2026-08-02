from __future__ import annotations

import pytest

from apix.agent.sdk.adapter.context.context_adapter import AIContextAdapter
from apix.agent.sdk.utils.message import (
    ApixAiMessage,
    ApixAiMessageChunk,
    ApixSystemMessage,
    ApixToolMessage,
    ApixUserMessage,
    ToolCallDelta,
)


def tool_message(call_id: str, content: str = "result") -> ApixToolMessage:
    return ApixToolMessage(
        content=content,
        name="tool",
        tool_call_id=call_id,
    )


def test_build_user_context_formats_and_escapes_every_supported_section():
    adapter = AIContextAdapter()
    context = adapter._build_user_context(
        {
            "referenced_message": {
                "role": "user",
                "name": "A&B",
                "content": "<hello>",
            },
            "active_file": "a<b.py",
            "uploaded_files": ["x&y.txt"],
            "task": {
                "type": "automated_task",
                "name": "daily <brief>",
                "prompt": "summarize & cite",
            },
        },
    )

    assert context.startswith("<context>\n")
    assert "<speaker>A&amp;B</speaker>" in context
    assert "<content>&lt;hello&gt;</content>" in context
    assert "<active_file>a&lt;b.py</active_file>" in context
    assert "./upload_files/x&amp;y.txt" in context
    assert "<name>daily &lt;brief&gt;</name>" in context
    assert "<prompt>summarize &amp; cite</prompt>" in context
    assert adapter._build_user_context({}) == ""


def testensure_tool_messages_reorders_deduplicates_and_fills_missing():
    adapter = AIContextAdapter()
    ai = ApixAiMessage(
        tool_calls=[
            {"call_id": "a", "tool_name": "first", "args": None},
            {"call_id": "b", "tool_name": "second", "args": {}},
        ]
    )
    first_b = tool_message("b", "B")
    duplicate_b = tool_message("b", "duplicate")
    unmatched = tool_message("other", "other")
    following = ApixUserMessage(content="next")
    messages = [ai, first_b, duplicate_b, unmatched, following]
    identity = id(messages)

    adapter.ensure_tool_message(messages)

    assert id(messages) == identity
    assert messages[0] is ai
    assert messages[1].tool_call_id == "a"
    assert messages[1].name == "first"
    assert messages[1].content == adapter._MISSING_TOOL_OUTPUT
    assert messages[2] is first_b
    assert messages[3] is following


@pytest.mark.parametrize(
    "tool_calls",
    [
        [{"tool_name": "x", "args": {}}],
        [{"call_id": "", "tool_name": "x", "args": {}}],
        [
            {"call_id": "same", "tool_name": "x", "args": {}},
            {"call_id": "same", "tool_name": "y", "args": {}},
        ],
    ],
)
def testensure_tool_messages_rejects_ambiguous_calls(tool_calls):
    with pytest.raises(ValueError):
        AIContextAdapter().ensure_tool_message(
            [ApixAiMessage(tool_calls=tool_calls)]
        )


def test_convert_persisted_messages_handles_todo_context_abort_and_json():
    adapter = AIContextAdapter()
    messages, todo = adapter.convert_to_apix_messages(
        [
            {
                "role": "info",
                "name": "todo",
                "extensions": {
                    "todo_list": [
                        {"content": "finish", "status": "in_progress"}
                    ]
                },
            },
            {
                "role": "ai",
                "name": "Alice",
                "content": "answer<conversation_abort>",
                "metadata": '{"provider":"test"}',
                "extensions": (
                    '{"reasoning":"why<conversation_abort>",'
                    '"tool_calls":[]}'
                ),
            },
            {
                "role": "user",
                "content": "continue",
                "extensions": {"active_file": "main.py"},
            },
        ],
        strict=False,
    )

    assert todo == [{"content": "finish", "status": "in_progress"}]
    assert messages[0].content == "answer"
    assert messages[0].reasoning == "why"
    assert messages[0].metadata == {"provider": "test"}
    assert "<active_file>main.py</active_file>" in messages[1].content


def test_convert_to_dict_message_filter_and_decode_helpers():
    adapter = AIContextAdapter()
    message = ApixAiMessage(
        message_uid="message-1",
        content="answer",
        reasoning="why",
    )

    assert adapter.convert_to_dict_message(
        message,
        "generation",
        filter=True,
    ) == {
        "role": "ai",
        "content": "answer",
        "extensions": {"reasoning": "why"},
    }
    assert adapter._decode_json_object('{"a":1}') == {"a": 1}
    assert adapter._decode_json_object("[]") == {}
    assert adapter._decode_json_object("invalid") == {}
    assert adapter._decode_json_object({"a": 1}) == {"a": 1}
    with pytest.raises(TypeError, match="ApixAiMessage or ApixToolMessage"):
        adapter.convert_to_dict_message(
            ApixUserMessage(content="no"),
            "generation",
        )


def test_drop_tool_messages_supports_complete_and_streamed_write_todos_calls():
    adapter = AIContextAdapter()
    before = tool_message("before")
    writer = ApixAiMessage(
        tool_calls=[
            {"call_id": "todo", "tool_name": "write_todos", "args": {}}
        ]
    )
    after = tool_message("after")

    dropped = adapter.drop_tool_messages(
        [before, writer, after],
        min_keep=0,
    )
    assert dropped[0].content == "[outdated]"
    assert dropped[2].content == "result"
    assert before.content == "result"

    streamed_writer = ApixAiMessageChunk(
        tool_call_deltas=(
            ToolCallDelta(index=0, tool_name_delta="write_todos"),
        )
    )
    dropped = adapter.drop_tool_messages(
        [before, streamed_writer, after],
        min_keep=0,
    )
    assert dropped[0].content == "[outdated]"

    generic = adapter.drop_tool_messages(
        [before],
        split_by_todos=False,
        min_keep=0,
    )
    assert generic[0].content == "[Tool Result Outdated]"
    with pytest.raises(ValueError, match="min_keep"):
        adapter.drop_tool_messages([before], min_keep=-1)


def test_split_messages_keeps_ai_tool_chain_together():
    adapter = AIContextAdapter()
    messages = [
        ApixUserMessage(content="old"),
        ApixAiMessage(
            tool_calls=[
                {"call_id": "a", "tool_name": "tool", "args": {}}
            ]
        ),
        tool_message("a"),
        ApixUserMessage(content="new"),
    ]

    summarized, recent = adapter.split_messages(messages, keep_recent=2)
    assert summarized == [messages[0]]
    assert recent == messages[1:]
    assert adapter.split_messages([], keep_recent=2) == ([], [])
    assert adapter.split_messages(messages, keep_recent=0) == (messages, [])
    assert adapter.split_messages(messages, keep_recent=10) == ([], messages)


def test_filter_apix_messages_handles_chunks_and_ignores_empty_ai_messages():
    adapter = AIContextAdapter()
    system = ApixSystemMessage(content="system")
    chunk = ApixAiMessageChunk(
        message_uid="chunk-id",
        reasoning_delta="why",
        content_delta="answer",
    )
    systems, messages, index = adapter.filter_apix_messages(
        [
            system,
            ApixUserMessage(content="question", name="user"),
            ApixAiMessage(content=None, reasoning=None),
            chunk,
            tool_message("ignored"),
        ]
    )

    assert systems == [system]
    assert systems[0] is not system
    assert messages[0].content == "question"
    assert messages[1].content == "why\n\nanswer"
    assert index == "chunk-id"
