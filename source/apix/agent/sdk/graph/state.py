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


class AgentConfigSchema(TypedDict):
    """
    Config for a single AI agent.
    """

    # User Info
    user_uid: str
    conversation_uid: str
    platform: str

    # LLM Runtime
    models_provider: str
    model_name: str
    api_key: str
    model_temperature: float
    custom_provider_id: NotRequired[str]

    enable_think: bool
    llm_calls_warning_threshold: int
    use_model_vision: bool  # If true, the picture will be sent to the LLM to analyze if the LLM supports picture input.

    # Agent Runtime Behavior
    workspace: str

    # Memory Strategy
    enable_longterm_memory: bool
    enable_shortterm_memory: bool  # If is true, message_summary node will invoke llm to compress else just truncate.
    summary_trigger_threshold: int  # If zero, not compress or truncate.
    summary_exempt_tail_length: int

    # Capabilities / Tools
    forbid_all_tool: bool  # If true, the agent will be a simple LLM without tools.
    enable_file_opration: bool
    enable_web_search: bool
    enable_knowledge_retrieval: bool
    enable_command_opration: bool
    enable_skill_load: bool
    enable_task_flow: bool
    enable_agent_assign: bool
    enable_agent_swarm: bool

    # Search engine config
    link_provider: str
    link_api_key: str
    content_provider: str
    content_api_key: str
    embed_model: str  # The embed model for knowledge retrieval.
    web_cleaner_mode: Literal["rule", "llm"]

    # Agent Identity / Prompt
    role_prompt: RoleSchema
    higher_role_prompt_permission: bool  # If true, the role prompt will insert into system prompt.


class GraphRuntimeContext(TypedDict):
    agent_name: str
    agent_role: Literal["team_leader", "team_worker", "main_agent", "sub_agent", "agent"]
    target: ApixIdentity
    generation_id: str
    node_id: NotRequired[str]
    parent_node_id: NotRequired[str]
    config: AgentConfigSchema
    timestamp: int


class MainAgentState(GraphRuntimeContext):
    input: dict
    re_generate: bool
    messages: Annotated[list[AnyMessage], AutoMerge]
    current_tool_calls: list
    longterm_memory: str # Cross-conversation longterm memory
    shortterm_memory: str # Recent summary
    rule_prompt: str
    runtime_prompt: str # Include todos prompt, workspace prompt, memorandum prompt and so on
    llm_calls: Annotated[int, AutoMerge] # Total LLM call count across the graph
    llm_retry_count: int
    error: NotRequired[str] # Error type
    error_detail: NotRequired[str] # Error detail
    context_compress_level: int # Level 0: Not compress; Level 1: Drop tool message content; Level 2: Context sumary to summary_exempt_tail_length; 
    context_fold_split_mark: NotRequired[str] # Split by completed | in_progress & pending todos, store with message id
    sandbox: str # Docker container id
    todos: NotRequired[list[Todo]]
    memorandum: NotRequired[list[LongtermMemory]]
    skills: list # Include available skills name and description
    loaded_skills_cache: list[tuple[str, bool, str]] # (name, injected, content): Skill name, injection status, and SKILL.md content


class SubAgentState(MainAgentState):
    final_goal: str
    task_id: str
    parent_task_id: str
    start_timestamp: int
    finish_timestamp: int
    status: Literal["in_progress", "completed", "pending", "failed", "cancelled"]
    outputs: Annotated[str, AutoMerge]
    errors: Annotated[str, AutoMerge]