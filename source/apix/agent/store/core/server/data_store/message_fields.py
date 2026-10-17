"""JSON persistence for Chat message columns shared by both SQL stores."""

import json
from typing import Any

CHAT_OPTIONAL_FIELDS = (
    "tool_calls", "refusal", "reasoning_content", "audio", "annotations", "function_call",
)
JSON_MESSAGE_FIELDS = ("tool_calls", "audio", "annotations", "function_call")


def encode_content(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def encode_optional(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def decode_message_row(row: dict, *, content_json: bool = False) -> dict:
    fields = JSON_MESSAGE_FIELDS
    if content_json:
        fields = ("content", *fields)
    for key in fields:
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])
    return row
