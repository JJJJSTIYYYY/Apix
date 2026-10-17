"""Opt-in MySQL verification in a fresh, disposable test database."""
import os
from uuid import uuid4

import aiomysql
import pytest

from apix.agent.core.utils.message import ApixAiMessage, ApixToolMessage
from apix.agent.prebuilt.adapter.context.context_adapter import AIContextAdapter
from apix.agent.store.core.server.data_store.mysql_server import MysqlService

pytestmark = pytest.mark.skipif(
    not os.environ.get("APIX_TEST_MYSQL_SOCKET"),
    reason="Set APIX_TEST_MYSQL_SOCKET to an isolated MySQL test instance",
)


@pytest.fixture
async def mysql_store():
    socket = os.environ["APIX_TEST_MYSQL_SOCKET"]
    database = f"apix_test_{uuid4().hex}"
    connection = await aiomysql.connect(
        unix_socket=socket, user="root", password="", autocommit=True,
    )
    service = MysqlService(
        host="localhost", port=3306, user="root", password="", database=database,
    )
    service._pool_args["unix_socket"] = socket
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(f"CREATE DATABASE {database} CHARACTER SET utf8mb4")
        await service.start()
        yield service
    finally:
        await service.stop()
        async with connection.cursor() as cursor:
            await cursor.execute(f"DROP DATABASE IF EXISTS {database}")
        connection.close()


@pytest.mark.parametrize("content", [None, "", "null", '[{"type":"text"}]', [
    {"type": "text", "text": "hello"},
    {"type": "image_url", "image_url": {"url": "https://example.test/a.png"}},
]])
async def test_initialized_mysql_stores_and_replays_chat_messages(mysql_store, content):
    db = mysql_store
    user = await db.create_a_user({"user_uid": "u1", "username": "test", "password": "test"})
    assert user["success"]
    conversation = await db.create_conversation({"user_uid": "u1"})
    assert conversation["success"]
    identity = {"user_uid": "u1", "conversation_uid": conversation["messages"]["conversation_uid"]}
    adapter = AIContextAdapter()
    assistant = ApixAiMessage(
        content=content, reasoning_content="why",
        tool_calls=[{"id": "c1", "type": "function", "function": {
            "name": "weather", "arguments": '{"city":"上海"}',
        }}],
        refusal="refusal", audio={"id": "a1"}, annotations=[],
        metadata={"usage": {"total_tokens": 3}},
        extensions={"uploaded_files": ["brief.pdf"], "custom": {"x": 1}},
    )
    tool = ApixToolMessage(content="", name="weather", tool_call_id="c1")
    for message in (assistant, tool):
        stored = adapter.convert_to_dict_message(message, "generation")
        result = await db.append_message({**identity, "message": stored})
        assert result["success"], result
    fetched = await db.fetch_messages_after_cursor(identity)
    assert fetched["success"], fetched
    restored, _ = adapter.convert_to_apix_messages(fetched["messages"])
    assert restored[0].to_chat() == assistant.to_chat()
    assert restored[0].extensions == assistant.extensions
    assert restored[0].metadata == assistant.metadata
    assert restored[1].to_chat() == tool.to_chat()
    assert [row["msg_cursor"] for row in fetched["messages"]] == [1, 2]
