
from typing import NotRequired, TypedDict, Annotated, Literal
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

class GraphRuntimeContext(TypedDict):
    agent_name: str
    agent_role: Literal["team_leader", "team_worker", "main_agent", "sub_agent", "agent"]
    client_id: str
    session_id: str
    history_id: str
    generation_id: str
    config: dict
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
