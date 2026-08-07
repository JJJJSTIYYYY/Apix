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


def test_build_user_context_uses_fallbacks_and_ignores_invalid_sections():
    adapter = AIContextAdapter()

    context = adapter._build_user_context(
        {
            "referenced_message": {"content": ""},
            "uploaded_files": "not-a-list",
            "task": {"name": "partial"},
        }
    )

    assert "<role>[UNKNOWN]</role>" in context
    assert "<speaker>[UNKNOWN]</speaker>" in context
    assert "<content>[CONTENT MISSED]</content>" in context
    assert "<uploaded_files>" not in context
    assert "<task>\n  <name>partial</name>\n</task>" in context
    assert adapter._build_user_context(
        {
            "referenced_message": [],
            "uploaded_files": {},
            "task": {"type": "", "name": "", "prompt": ""},
        }
    ) == ""


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


def test_ensure_tool_message_handles_empty_and_non_tool_call_messages():
    adapter = AIContextAdapter()
    messages = [
        ApixUserMessage(content="question"),
        ApixAiMessage(content="answer"),
    ]

    adapter.ensure_tool_message([])
    adapter.ensure_tool_message(messages)

    assert len(messages) == 2


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


def test_convert_persisted_messages_covers_all_roles_defaults_and_skips():
    adapter = AIContextAdapter()
    messages, todo = adapter.convert_to_apix_messages(
        [
            {"role": "user", "content": ""},
            {
                "role": "user",
                "message_uid": "user-id",
                "name": "Alice",
                "content": "question",
            },
            {"role": "ai", "content": ""},
            {
                "role": "ai",
                "content": "",
                "extensions": {
                    "tool_calls": [
                        {
                            "call_id": "call-1",
                            "tool_name": "search",
                            "args": {},
                        }
                    ]
                },
            },
            {"role": "tool", "content": ""},
            {
                "role": "tool",
                "name": "search",
                "content": "result",
                "extensions": {"tool_call_id": "call-1"},
            },
            {"role": "system", "content": ""},
            {"role": "system", "content": "rules"},
            {
                "role": "info",
                "name": "todo",
                "extensions": {
                    "todo_list": [
                        {"content": "done", "status": "completed"}
                    ]
                },
            },
            {"role": "unknown", "content": "ignored"},
        ],
    )

    assert todo is None
    assert [message.role for message in messages] == [
        "user",
        "ai",
        "tool",
        "system",
    ]
    assert messages[0].message_uid == "user-id"
    assert messages[0].name == "Alice"
    assert messages[1].name == "assistant"
    assert messages[2].tool_call_id == "call-1"
    assert messages[3].name == "system"


def test_convert_persisted_messages_strict_mode_fills_missing_tool_output():
    messages, _ = AIContextAdapter().convert_to_apix_messages(
        [
            {
                "role": "ai",
                "extensions": {
                    "tool_calls": [
                        {
                            "call_id": "missing",
                            "tool_name": "search",
                            "args": None,
                        }
                    ]
                },
            }
        ]
    )

    assert len(messages) == 2
    assert isinstance(messages[1], ApixToolMessage)
    assert messages[1].tool_call_id == "missing"


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


def test_convert_tool_message_to_full_dict_uses_independent_payloads():
    adapter = AIContextAdapter()
    message = ApixToolMessage(
        message_uid="tool-id",
        name="search",
        content="result",
        metadata={"duration": 1},
        extensions={"custom": {"value": 1}},
        tool_call_id="call-1",
    )

    result = adapter.convert_to_dict_message(
        message,
        "generation-id",
        parent_id="parent-id",
    )

    assert result == {
        "message_uid": "tool-id",
        "generation_id": "generation-id",
        "role": "tool",
        "name": "search",
        "content": "result",
        "node_id": "eneration-id-apix",
        "parent_id": "parent-id",
        "metadata": {"duration": 1},
        "extensions": {
            "custom": {"value": 1},
            "tool_call_id": "call-1",
        },
    }
    result["metadata"]["duration"] = 2
    result["extensions"]["custom"]["value"] = 2
    assert message.metadata == {"duration": 1}
    assert message.extensions["custom"] == {"value": 1}

    filtered = adapter.convert_to_dict_message(
        ApixToolMessage(content="", tool_call_id="call-2"),
        "generation-id",
        filter=True,
    )
    assert filtered == {
        "role": "tool",
        "content": "",
        "extensions": {"tool_call_id": "call-2"},
    }


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


def test_drop_tool_messages_preserves_empty_input_tail_and_non_tool_messages():
    adapter = AIContextAdapter()
    user = ApixUserMessage(content="question")
    old_tool = tool_message("old")
    recent_tool = tool_message("recent")

    assert adapter.drop_tool_messages([]) == []
    dropped = adapter.drop_tool_messages(
        [user, old_tool, recent_tool],
        split_by_todos=False,
        min_keep=1,
    )

    assert dropped[0] is user
    assert dropped[1].content == "[Tool Result Outdated]"
    assert dropped[2] is recent_tool


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


def test_split_messages_auto_mode_uses_latest_user_or_keeps_everything():
    adapter = AIContextAdapter()
    first = ApixAiMessage(content="old")
    user = ApixUserMessage(content="latest")
    answer = ApixAiMessage(content="answer")

    assert adapter.split_messages([first, user, answer]) == (
        [first],
        [user, answer],
    )
    assert adapter.split_messages([first, answer]) == (
        [],
        [first, answer],
    )


def test_split_messages_handles_complete_and_orphan_tool_blocks():
    adapter = AIContextAdapter()
    ai = ApixAiMessage(
        tool_calls=[
            {"call_id": "a", "tool_name": "tool", "args": {}},
            {"call_id": "b", "tool_name": "tool", "args": {}},
        ]
    )
    first_tool = tool_message("a")
    second_tool = tool_message("b")
    tail = ApixUserMessage(content="tail")

    summarized, recent = adapter.split_messages(
        [ai, first_tool, second_tool, tail],
        keep_recent=2,
    )
    assert summarized == []
    assert recent == [ai, first_tool, second_tool, tail]

    summarized, recent = adapter.split_messages(
        [ai, first_tool, second_tool, tail],
        keep_recent=3,
    )
    assert summarized == []
    assert recent == [ai, first_tool, second_tool, tail]

    orphan_prefix = ApixUserMessage(content="prefix")
    summarized, recent = adapter.split_messages(
        [orphan_prefix, first_tool, second_tool, tail],
        keep_recent=2,
    )
    assert summarized == [orphan_prefix, first_tool, second_tool]
    assert recent == [tail]


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


def test_filter_apix_messages_can_drop_reasoning_and_keep_ai_content():
    ai = ApixAiMessage(
        message_uid="ai-id",
        content="answer",
        reasoning="private reasoning",
        name="Alice",
    )

    systems, messages, index = AIContextAdapter().filter_apix_messages(
        [ai],
        keep_reasoning=False,
    )

    assert systems == []
    assert len(messages) == 1
    assert messages[0].content == "answer"
    assert messages[0].name == "Alice"
    assert index == "ai-id"
