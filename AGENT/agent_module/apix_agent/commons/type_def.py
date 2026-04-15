
from typing import Any, NotRequired, TypedDict, Annotated, Literal
import operator
from langchain_core.messages import AnyMessage 
from langchain.agents.middleware.todo import Todo

# Role mode in GraphRuntimeContext:

# - agent:
#   Normal role. This agent chats directly with the user,
#   but does not have permission to assign a sub-agent.

# - main_agent:
#   Main agent role. This agent chats directly with the user
#   and has permission to assign one sub-agent per user request.

# - sub_agent:
#   Sub-agent role. This agent does not chat directly with the user
#   and has no permission to assign sub-agents. It acts as a task executor for a main agent.

# - team_leader:
#   Main agent role. This agent chats directly with the user
#   and has permission to assign multiple sub-agents per user request.

# - team_worker:
#   Sub-agent role. This agent does not chat directly with the user
#   and has no permission to assign sub-agents. It acts as a task executor in an agent team.


class RoleSchema(TypedDict):
    name: str
    definition: str


class AgentConfigSchema(TypedDict):
    """
    Config for a single AI agent.
    """

    # LLM Runtime
    models_provider: str
    model_name: str
    api_key: str

    enable_think: bool
    max_chunk_per_invoking: int
    use_model_vision: bool  # If true, the picture will be sent to the LLM to analyze if the LLM supports picture input.


    # Agent Runtime Behavior
    work_dir: str
    async_tools_invoke: bool
    save_async_tools_message: bool  # If true, async returns will save to database.
    pure_chat_on: bool  # If true, the agent will be a simple LLM without tools.


    # Memory Strategy
    enable_longterm_memory: bool
    enable_shortterm_memory: bool  # If is true, message_summary node will invoke llm to compress else just truncate.
    summary_trigger_threshold: int  # If zero, not compress or truncate.
    summary_exempt_tail_length: int


    # Capabilities / Tools
    enable_file_opration: bool
    enable_web_search: bool
    enable_knowledge_retrieval: bool
    enable_command_opration: bool
    enable_skill_load: bool
    enable_agent_assign: bool
    enable_agent_swarm: bool


    # External Services
    link_provider: str
    link_api_key: str
    content_provider: str
    content_api_key: str
    embed_model: str  # The embed model for knowledge retrieval.
    web_cleaner_mode: str


    # Agent Identity / Prompt
    role_prompt: RoleSchema
    higher_role_prompt_permission: bool  # If true, the role prompt will insert into system prompt.
    

class GraphRuntimeContext(TypedDict):
    agent_name: str
    agent_role: Literal["team_leader", "team_worker", "main_agent", "sub_agent", "agent"]
    client_id: str
    session_id: str
    history_id: str
    generation_id: str
    config: AgentConfigSchema
    timestamp: int


class MessagesState(GraphRuntimeContext):
    input: dict
    messages: Annotated[list[AnyMessage], operator.add]
    current_tool_calls: list
    longterm_memory: str # Cross-conversation longterm memory
    shortterm_memory: str # Recent summary
    rule_prompt: str
    runtime_prompt: str # Include todos prompt, workspace prompt, memorandum prompt and so on
    llm_calls: Annotated[int, operator.add] # Total LLM call count across the graph
    # generated_messages_length: Annotated[int, operator.add]
    sandbox: str # Docker container id
    todos: NotRequired[list[Todo]]
    memorandum: NotRequired[list[str]]
    skills: list # Include available skills name and description
    documents: list # Include available documents name and description



class SubAssistantState(MessagesState):
    final_goal: str
    task_id: str
    parent_task_id: str
    start_timestamp: int
    finish_timestamp: int
    status: Literal["in_progress", "completed", "pending", "failed", "cancelled"]
    outputs: Annotated[str, operator.add]
    errors: Annotated[str, operator.add]