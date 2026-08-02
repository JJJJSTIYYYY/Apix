from typing import Annotated, Literal, NotRequired, TypedDict

from apix.agent.sdk.utils.message import AnyMessage
from apix.common.type import ApixIdentity
from apix.core.graph.base import AutoMerge


class RoleSchema(TypedDict):
    name: str
    definition: str


class Todo(TypedDict):
    content: str
    status: Literal["pending", "in_progress", "completed"]


class Skill(TypedDict):
    skill_id: str
    skill_name: str
    description: Literal["pending", "in_progress", "completed"]


class LongtermMemory(TypedDict):
    memory_id: str # Longterm memory id, uuid4 hex.
    title: str
    date: str # 2025-06-07
    content: str
    source: Literal["conversation", "workspace"]


class ShorttermMemory(TypedDict):
    memory_id: str # The related message's ``message_uid``.
    content: str
    created_timestamp: int # Linux timestamp