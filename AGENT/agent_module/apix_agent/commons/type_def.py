
from typing import Any, NotRequired, Required, TypedDict, Annotated, Literal
import operator
from langchain_core.messages import AnyMessage 
from langchain.agents.middleware.todo import Todo


class ProviderNotFound(Exception):
    
    def __init__(self, message="Custom provider not found.", provider=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = provider if provider else ''
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"


class PlatformNotRegister(Exception):
    
    def __init__(self, message="Platform not register error.", platform=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = platform if platform else ''
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"


class ConflictToolCalls(Exception):
    
    def __init__(self, message="Invalid tool calls detected", errors=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = errors if errors else []
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"


class InvalidOutputsError(Exception):
    
    def __init__(self, message="Invalid outputs detected", errors=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = errors if errors else []
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"
    

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



class ApixEventEnvelopeTarget(TypedDict):
    id: str
    platform: str
    conversation_id: str


class RoleSchema(TypedDict):
    name: str
    definition: str


class MemoItem(TypedDict):
    title: str
    date: str # 2025-06-07
    content: str
    source: Literal["conversation", "workspace"]


class AgentConfigSchema(TypedDict):
    """
    Config for a single AI agent.
    """

    # User / Session Info
    client_id: str
    session_id: str
    history_id: str
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
    work_dir: str
    keep_tools_message: bool  # If true, async returns will save to database.
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
    enable_task_flow: bool
    enable_agent_assign: bool
    enable_agent_swarm: bool


    # External Services
    link_provider: str
    link_api_key: str
    content_provider: str
    content_api_key: str
    embed_model: str  # The embed model for knowledge retrieval.
    web_cleaner_mode: str
    auto_save_config: bool  # If true, the agent config will auto save when changed.


    # Agent Identity / Prompt
    role_prompt: RoleSchema
    higher_role_prompt_permission: bool  # If true, the role prompt will insert into system prompt.


class ApixPayloadSchema(TypedDict):
    client_id: str
    session_id: str
    history_id: str
    platform: str
    messages: dict
    re_generate: bool
    config: AgentConfigSchema


class ApixEntryDataSchema(TypedDict):
    action: str
    data: ApixPayloadSchema | Any


class GraphRuntimeContext(TypedDict):
    agent_name: str
    agent_role: Literal["team_leader", "team_worker", "main_agent", "sub_agent", "agent"]
    client_id: str
    session_id: NotRequired[str]
    history_id: str
    target: ApixEventEnvelopeTarget
    generation_id: str
    node_id: NotRequired[str]
    parent_node_id: NotRequired[str]
    config: AgentConfigSchema
    timestamp: int


class MainAgentState(GraphRuntimeContext):
    input: dict
    re_generate: bool
    messages: Annotated[list[AnyMessage], operator.add]
    current_tool_calls: list
    longterm_memory: str # Cross-conversation longterm memory
    shortterm_memory: str # Recent summary
    rule_prompt: str
    runtime_prompt: str # Include todos prompt, workspace prompt, memorandum prompt and so on
    llm_calls: Annotated[int, operator.add] # Total LLM call count across the graph
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
    status: Literal["in_progress", "done", "completed", "pending", "failed", "cancelled"]
    outputs: Annotated[str, operator.add]
    errors: Annotated[str, operator.add]


class MinimalEnvelopeData(TypedDict, total=False):
    event_name: Required[str]
    content: Required[Any]


class ApixEventEnvelope(TypedDict):
    event: str
    target: ApixEventEnvelopeTarget
    generation_id: str
    data: MinimalEnvelopeData          # main payload
    timestamp: float
    blocking: bool
    block_id: NotRequired[str]



class McpMetaSchema(TypedDict):
    mcp_id: str
    mcp_name: str
    transport: Literal["stdio", "http", "streamable_http", "websocket", "sse"]
    endpoint: str # For stdio, it's the command to start the MCP server. For http/websocket/sse, it's the URL to connect.
    config: dict[str, Any]