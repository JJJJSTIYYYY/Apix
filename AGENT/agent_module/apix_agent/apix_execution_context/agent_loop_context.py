import copy
from typing import Literal

import httpx
from langchain_core.messages import AnyMessage
from langchain.agents.middleware.todo import Todo

from apix_agent.commons.common_func import convert_generation_id_to_message_node_id
from apix_agent.commons.type_def import AgentConfigSchema, MainAgentState, MemoItem, SubAgentState, ApixIdentity
from apix_agent.global_config import MEMORY_SERVICE_BASE_URL
from apix_agent.apix_execution_context.execution_context_base import ExecutionContextBase


class AgentLoopContext(ExecutionContextBase):

    # GraphRuntimeContext
    agent_name: str
    agent_role: Literal["team_leader", "team_worker", "main_agent", "sub_agent", "agent"]
    client_id: str
    session_id: str
    history_id: str
    target: ApixIdentity
    generation_id: str
    node_id: str
    parent_node_id: str
    config: AgentConfigSchema
    timestamp: int

    # MainAgentState
    input: dict
    re_generate: bool
    messages: list[AnyMessage]
    current_tool_calls: list
    longterm_memory: str
    shortterm_memory: str
    rule_prompt: str
    runtime_prompt: str
    llm_calls: int
    llm_retry_count: int
    error: str
    error_detail: str
    context_compress_level: int
    context_fold_split_mark: str
    sandbox: str
    todos: list[Todo]
    memorandum: list[MemoItem]
    skills: list
    loaded_skills_cache: list[tuple[str, bool, str]]
    documents: list

    # SubAgentState
    final_goal: str
    task_id: str
    parent_task_id: str
    start_timestamp: int
    finish_timestamp: int
    status: Literal["in_progress", "completed", "pending", "failed", "cancelled"]
    outputs: str
    errors: str

    def __init__(
        self,
        agent_state: MainAgentState | SubAgentState,
    ):
        super().__init__()

        agent_state = copy.deepcopy(agent_state)
        agent_state_group = []

        for k, v in agent_state.items():
            agent_state_group.append(k)
            setattr(self, k, v)

        self.register_a_group(
            "agent_state",
            agent_state_group,
            exist_ok=True,
        )


    async def get_current_message_chain(self, contain_current_node: bool = False) -> list[str]:
        """
        Get current message chain, returns a node_id list.

        Args:
            contain_current_node (bool): If contain the current message node id.
                Warn: current node may not append in database at now.
        """
        response = await httpx.AsyncClient().post(
            f"{MEMORY_SERVICE_BASE_URL}/memory/user/current_chain_id",
            json={
                "client_id": self.client_id,
                "history_id": self.history_id
            },
        )
        response.raise_for_status()
        message_chain = response.json().get("messages", []) or []

        if contain_current_node:
            node_id = convert_generation_id_to_message_node_id(self.generation_id, 'ai')
            message_chain.append(node_id)

        return message_chain
    
    @classmethod
    async def get_cached_message_chain(cls, target: ApixIdentity) -> list[str]:
        """
        Get cached message chain, returns a node_id list.

        Args:
            target (ApixIdentity)
        """
        response = await httpx.AsyncClient().post(
            f"{MEMORY_SERVICE_BASE_URL}/memory/user/current_chain_id",
            json={
                "client_id": target.get("id"),
                "history_id": target.get("conversation_id")
            },
        )
        response.raise_for_status()
        message_chain = response.json().get("messages", []) or []

        return message_chain

