"""Persistence of canonical Chat messages in newly initialized databases."""
import json

import pytest

from apix.agent.core.utils.message import ApixAiMessage, ApixSystemMessage, ApixToolMessage, ApixUserMessage
from apix.agent.prebuilt.adapter.context.context_adapter import AIContextAdapter
from apix.agent.store.core.server.data_store.sqlite_server import SqliteService
from tests.agent.store.server.test_sqlite_server import create_user_and_conversation


@pytest.mark.parametrize("content", [None, "", "null", '[{"type":"text"}]', [
    {"type": "text", "text": "look"}, {"type": "image_url", "image_url": {"url": "https://example.test/a.png"}}]])
async def test_sqlite_content_and_protocol_fields_round_trip(tmp_path, monkeypatch, content):
    db = SqliteService(tmp_path / "chat.sqlite3")
    await db.start()
    try:
        await create_user_and_conversation(db, monkeypatch)
        call = {"id": "c1", "type": "function", "function": {"name": "weather", "arguments": '{"city":"上海"}'}}
        message = ApixAiMessage(content=content, tool_calls=[call], refusal="refusal",
                                reasoning_content="why", audio={"id": "audio-1"}, annotations=[],
                                metadata={"usage": {"total_tokens": 3}},
                                extensions={"uploaded_files": ["brief.pdf"], "custom": {"x": 1}})
        adapter = AIContextAdapter()
        stored = adapter.convert_to_dict_message(message, "generation")
        payload = {"user_uid": "user-1", "conversation_uid": "conv-1", "message": stored}
        assert (await db.append_message(payload))["success"]
        tool = ApixToolMessage(content="", tool_call_id="c1", extensions={"active_file": "notes.md"})
        assert (await db.append_message({**payload, "message": adapter.convert_to_dict_message(tool, "generation")}))["success"]
        fetched = await db.fetch_messages_after_cursor(payload)
        assert fetched["success"]
        row = fetched["messages"][0]
        assert row["content"] == content
        assert row["tool_calls"] == [call]
        assert row["audio"] == {"id": "audio-1"}
        restored, _ = adapter.convert_to_apix_messages(fetched["messages"])
        assert restored[0].to_chat() == message.to_chat()
        assert restored[0].extensions == message.extensions
        assert restored[0].metadata == message.metadata
        assert restored[1].tool_call_id == "c1" and restored[1].content == ""
    finally:
        await db.stop()


async def test_context_preserves_multimodal_user_and_developer():
    parts = [{"type": "image_url", "image_url": {"url": "https://example.test/a.png"}}]
    messages, _ = AIContextAdapter().convert_to_apix_messages([
        {"role": "system", "content": "rules"},
        {"role": "user", "content": parts, "extensions": {"active_file": "notes.md"}},
    ])
    assert isinstance(messages[0], ApixSystemMessage)
    assert messages[1].content[-1] == parts[0]
    assert "<active_file>" in messages[1].content[0]["text"]
    assert parts == [{"type": "image_url", "image_url": {"url": "https://example.test/a.png"}}]

