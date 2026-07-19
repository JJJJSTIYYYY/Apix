from typing import Annotated, Literal, NotRequired, TypedDict

from apix.agent.common.message import AnyMessage
from apix.agent.common.type import AgentConfigSchema, MemoItem, Todo
from apix.common.type.global_type import ApixIdentity


class GraphRuntimeContext(TypedDict):
    agent_name: str
    agent_role: Literal["team_leader", "team_worker", "main_agent", "sub_agent", "agent"]
    user_uid: str
    conversation_uid: str
    target: ApixIdentity
    generation_id: str
    node_id: NotRequired[str]
    parent_node_id: NotRequired[str]
    config: AgentConfigSchema
    timestamp: int


class MainAgentState(GraphRuntimeContext):
    input: dict
    re_generate: bool
    messages: list[AnyMessage]
    current_tool_calls: list
    longterm_memory: str # Cross-conversation longterm memory
    shortterm_memory: str # Recent summary
    rule_prompt: str
    runtime_prompt: str # Include todos prompt, workspace prompt, memorandum prompt and so on
    llm_calls: int # Total LLM call count across the graph
    llm_retry_count: int
    error: NotRequired[str] # Error type
    error_detail: NotRequired[str] # Error detail
    context_compress_level: int # Level 0: Not compress; Level 1: Drop tool message content; Level 2: Context sumary to summary_exempt_tail_length; 
    context_fold_split_mark: NotRequired[str] # Split by completed | in_progress & pending todos, store with message id
    sandbox: str # Docker container id
    todos: NotRequired[list[Todo]]
    memorandum: NotRequired[list[MemoItem]]
    skills: list # Include available skills name and description
    loaded_skills_cache: list[tuple[str, bool, str]] # (name, injected, content): Skill name, injection status, and SKILL.md content
    documents: list # Include available documents name and description


class SubAgentState(MainAgentState):
    final_goal: str
    task_id: str
    parent_task_id: str
    start_timestamp: int
    finish_timestamp: int
    status: Literal["in_progress", "completed", "pending", "failed", "cancelled"]
    outputs: str
    errors: str