from typing import NotRequired, TypedDict


class BasicInfo(TypedDict):
    client_id: str
    history_id: str
    session_id: str | None
    # Allow extra optional fields
    extra: NotRequired[object]


class TaskInfo(TypedDict):
    task_id: str
    client_id: str | None
    history_id: str | None
    payload: dict | None # function calling params include task info, such as task name, params, etc.
    status: str
    result: dict | None


class Message(TypedDict):
    role: str
    content: str
    extra: dict | None


class MessageDict(TypedDict):
    client_id: str
    history_id: str
    session_id: str | None
    messages: list[Message]
    