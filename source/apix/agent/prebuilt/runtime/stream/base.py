from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Required, TypedDict

from apix.common.type import ApixIdentity


class AgentStreamChunkType(str, Enum):
    ESSENTIAL_INFO_RETURN = 'essential_info_return'
    LLM_STREAM_START = "llm_stream_start"
    LLM_CHUNK_RETURN = "llm_chunk_return"
    LLM_STREAM_END = "llm_stream_end"
    LLM_STREAM_ERROR = "llm_stream_error"
    AI_MESSAGE_RETURN = "ai_message_return"
    TOOL_MESSAGE_RETURN = "tool_message_return"
    TOOL_EXEC_START = "tool_exec_start"
    TOOL_EXEC_CHUNK = "tool_exec_chunk"
    TOOL_EXEC_END = "tool_exec_end"
    RUNTIME_WARNING = "runtime_warning"
    ERROR_OCCURRED = "error_occurred"


class MinimalChunkData(TypedDict, total=False):
    chunk_name: Required[str]
    content: Required[Any] # Serializable object


class AgentStreamChunk(TypedDict):
    chunk_id: str
    chunk_type: AgentStreamChunkType
    generation_id: str
    target: ApixIdentity
    data: MinimalChunkData
    timestamp: float