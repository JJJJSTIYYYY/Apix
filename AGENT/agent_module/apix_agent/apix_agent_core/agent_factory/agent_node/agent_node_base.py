from abc import ABC, abstractmethod
import asyncio
import copy

from langchain.chat_models import BaseChatModel
from langgraph.graph.state import Command
from langgraph.graph import END
from langchain_core.messages import AIMessageChunk, ToolMessage, AIMessage

from apix_agent.apix_agent_core.agent_factory.prompt import *
from apix_agent.commons.type_def import InvalidOutputsError, MainAgentState, ConflictToolCalls
from apix_agent.commons.logger import logger
from apix_agent.commons.common_func import get_date_natural_language
from apix_agent.apix_agent_core.tools.registry import conflict_tool_set


class AgentNodeBase(ABC):

    def __init__(self, llm: BaseChatModel, tool_set: list[str]):
        self.llm: BaseChatModel = llm
        self.tool_set: list[str] = tool_set

        self.SYSTEM_ALERT_PROMPT = "[SYSTEM ALERT] Task execution time is too long. Expedite immediately."
        self.SUMMARY_MEMORY_PREFIX = "Here is the existing compression of this conversation:\n\n"
        self.SUMMARY_INSTRUCTION_PROMPT = (
            "Compress all preceding messages and update the existing compression into the required structured format.\n"
            "** Use the same language as the original conversation for all content. **\n"
            "** Do NOT translate or modify the section headers. **\n"
            "** Section headers MUST remain exactly as specified in English. **"
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
        threshold: int,
    ) -> bool:
        """
        Determine whether to inject system alert message.
        """

        next_llm_calls = llm_calls + 1

        if next_llm_calls == threshold:
            return True

        return False
    

    def _ensure_agent_message(self, agent_message: AIMessage | AIMessageChunk, reasoning: bool = False) -> AIMessage | AIMessageChunk:
        agent_message = copy.deepcopy(agent_message)
        tool_calls = agent_message.tool_calls
        content = agent_message.content
        think = agent_message.additional_kwargs.get('reasoning_content')
        fallback_content = "Continue."
        if tool_calls: 
            fallback_content = fallback_content + " Call tools: "
            seen = set()
            tool_names = set()
            has_error = False
            for tool in tool_calls:
                tool_name = tool.get("name", "")
                tool_names.add(tool_name)
                if not tool_name:
                    raise ConflictToolCalls("Can not use empty tool name")
                if tool_name in conflict_tool_set:
                    if tool.get("name") not in seen:
                        seen.add(tool_name)
                    else:
                        has_error = True
            fallback_content = fallback_content + ', '.join(tool_names) + '.'

            if has_error:
                raise ConflictToolCalls(f"Tool {', '.join(seen)} are not allowed to be called simultaneously in one tool_calls")
            
        if not content and not think and tool_calls: 
            if reasoning: 
                agent_message.additional_kwargs['reasoning_content'] = fallback_content
            else:
                agent_message.content = fallback_content
        elif not content and not think and not tool_calls: 
            raise InvalidOutputsError("Empty ai message detected")

        return agent_message


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
    
    async def route_after_llm(self, state: MainAgentState):
        exception_type = state.get("error")
        if state.get("llm_retry_count", 0) > 0 and exception_type:
            logger.warning(f"Redirect to llm call because of {exception_type}")
            if exception_type == "others":
                return "retry"
            elif exception_type == "rate_limit":
                await asyncio.sleep(5)
                return "retry"
            elif exception_type == "token_exceed":
                return "summary"
        return "ok"
        

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
