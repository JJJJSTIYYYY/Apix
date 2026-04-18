from abc import ABC, abstractmethod

from langchain.chat_models import BaseChatModel
from langgraph.graph.state import Command
from langgraph.graph import END
from langchain_core.messages import AIMessageChunk, ToolMessage, AIMessage

from apix_agent.apix_agent_core.agent_factory.prompt import *
from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.commons.type_def import MainAgentState
from apix_agent.commons.logger import logger
from apix_agent.commons.common_func import get_date_natural_language


class AgentNodeBase(ABC):

    def __init__(self, llm: BaseChatModel, tool_set: list[str]):
        self.llm: BaseChatModel = llm
        self.tool_set: list[str] = tool_set

        self.SYSTEM_ALERT_PROMPT = "[SYSTEM ALERT] Task execution time is too long. Expedite immediately."
        self.SUMMARY_MEMORY_PREFIX = "Here is the existing compression of this conversation:\n"
        self.SUMMARY_INSTRUCTION_PROMPT = (
            "Compress all preceding messages into the required structured format.\n"
            "Use the same language as the original conversation for all content.\n"
            "Do NOT translate or modify the section headers.\n"
            "Section headers MUST remain exactly as specified in English."
        )


    def _load_prompt(self, agent_role: str = "agent") -> str:
        if agent_role in ['team_leader', 'main_agent']:
            base = DEFAULT_LEADER_PROMPT
        elif agent_role == 'agent':
            base = DEFAULT_AGENT_PROMPT
        else:
            base = DEFAULT_WORKER_PROMPT

        # Deduplicate tools by name (preserve order)
        unique_tools = []
        for tool in self.tool_set:
            if tool not in unique_tools:
                unique_tools.append(tool)

        if unique_tools:
            tool_list_text = "\n".join(f"- {name}" for name in unique_tools)
        else:
            tool_list_text = "No tools available."

        tools_block = DEFAULT_TOOLS_PROMPT.format(
            tool_list=tool_list_text
        )

        time_msg = get_date_natural_language()

        final_prompt = (
            time_msg
            + "\n\n"
            + base
            + "\n\n"
            + tools_block
        )

        return final_prompt

        
    def _should_inject_alert(
        self,
        llm_calls: int,
        llm_calls_warning_threshold: int,
        summary_exempt_tail_length: int,
    ) -> bool:
        """
        Determine whether to inject system alert message.

        Rules:
        1. First time reaching threshold -> alert
        2. After threshold -> periodically alert based on summary_exempt_tail_length
        """

        next_llm_calls = llm_calls + 1
        threshold = llm_calls_warning_threshold

        # First hit threshold
        if next_llm_calls == threshold:
            return True

        # After threshold
        if next_llm_calls > threshold:
            exceed_count = next_llm_calls - threshold
            if summary_exempt_tail_length > 0:
                trigger_round = exceed_count // summary_exempt_tail_length
                if trigger_round >= 1:
                    return True

        return False


    def should_continue(self, state: MainAgentState):
        """
        Decide whether to enter tool execution loop.
        """
        logger.trace('[node_base.py] [AgentNodeBase] [should_continue] Enter')
        if not state.get("messages"):
            return END
        last_message = state["messages"][-1]
        if (isinstance(last_message, AIMessage) or isinstance(last_message, AIMessageChunk)) and last_message.tool_calls:
            return "tools"
        elif isinstance(last_message, ToolMessage):
            return "llm"
        return END
        

    @abstractmethod
    async def context_prepare(self, state: MainAgentState) -> Command:
        pass
        

    @abstractmethod
    async def context_summary(self, state: MainAgentState) -> Command:
        pass
    

    @abstractmethod
    async def llm_call(self, state: MainAgentState) -> Command:
        pass
    
    
    @abstractmethod
    async def messages_persist(self, state: MainAgentState) -> Command:
        pass
