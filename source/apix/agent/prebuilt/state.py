from typing import Annotated, Literal, NotRequired, TypedDict

from apix.agent.sdk.utils.message import AnyMessage, ToolCall
from apix.common.type import ApixIdentity
from apix.core.graph.base import AutoMerge
from apix.agent.sdk.utils.context import LongtermMemory, ShorttermMemory, Skill, Todo, RoleSchema


class LLMConfig(TypedDict):
    model_provider: str
    model_name: str
    api_key: str
    model_temperature: float
    custom_provider_id: NotRequired[str]
    enable_think: bool
    role_prompt: RoleSchema


class WebSearchConfig(TypedDict):
    keyword_search_provider: str
    keyword_search_api_key: str
    url_filter: dict # Include `must_contains` and `not_contains` key.
    web_scraping_provider: str
    web_scraping_api_key: str
    web_cleaner_model_config: LLMConfig | None


class AgentVisionConfig(TypedDict):
    vision_pattern: Literal["easy_ocr", "llm"]
    vision_model_config: LLMConfig | None


class AgentMemoryConfig(TypedDict):
    enable_longterm_memory: bool
    enable_shortterm_memory: bool  # If is true, message_summary node will invoke llm to compress else just truncate.
    summary_trigger_threshold: int  # If zero, not compress or truncate.
    summary_exempt_tail_length: int


class ToolPermissionConfig(TypedDict):
    forbid_all_tool: bool  # If true, the agent will be a simple LLM without tools.
    enable_file_opration: bool
    enable_web_search: bool
    enable_knowledge_retrieval: bool
    enable_command_opration: bool
    enable_skill_load: bool
    enable_agent_assign: bool


class AgentSandboxConfig(TypedDict):
    sandbox_type: Literal["builtin", "docker"]
    workspace: str


class AgentConfigSchema(TypedDict):
    """
    Config for a single AI agent.
    """
    agent_role: Literal["leader", "worker", "agent"]

    # LLM
    llm_config: LLMConfig

    # Vision
    vision_config: AgentVisionConfig
    
    # Runtime
    sandbox_config: AgentSandboxConfig

    # Memory Config
    memory_config: AgentMemoryConfig

    # Tools
    tool_permission: ToolPermissionConfig

    # Web Search Config
    web_search_config: WebSearchConfig

    llm_calls_warning_threshold: int


class AgentState(TypedDict):
    target: ApixIdentity
    generation_id: str
    re_generate: bool

    # Node Information
    node_id: str
    parent_node_id: str

    # Messages state
    input: dict
    messages: Annotated[list[AnyMessage], AutoMerge]
    current_tool_calls: list[ToolCall]
    shortterm_memory: NotRequired[ShorttermMemory] # Recent summary
    longterm_memory: NotRequired[list[LongtermMemory]]
    todos: NotRequired[list[Todo]]
    skills: NotRequired[list[Skill]] # Include available skills name and description

    # Running State
    llm_calls: Annotated[int, AutoMerge] # Total LLM call count across the graph
    llm_retry_count: int
    error_type: NotRequired[str] # Error type
    error_detail: NotRequired[str] # Error detail
    context_compress_level: int # Level 0: Not compress; Level 1: Drop tool message content; Level 2: Context sumary to summary_exempt_tail_length; 
    context_fold_split_mark: NotRequired[str] # Split by completed | in_progress & pending todos, store with message id
    sandbox: str # Docker container id
    config: AgentConfigSchema


class SubAgentState(AgentState):
    final_goal: str
    task_id: str
    start_timestamp: int
    finish_timestamp: int
    status: Literal["in_progress", "completed", "pending", "failed", "cancelled"]
    outputs: Annotated[str, AutoMerge]
    errors: Annotated[str, AutoMerge]