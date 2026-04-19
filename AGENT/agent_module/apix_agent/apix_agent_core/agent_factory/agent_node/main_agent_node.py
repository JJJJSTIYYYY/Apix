import asyncio
import time

from langchain.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessageChunk, HumanMessage, ToolMessage, AIMessage
from langgraph.graph import END
from langgraph.graph.state import Command
from langgraph.types import Overwrite

from apix_agent.apix_event_pipe.stream_writer import ApixStreamWriter, StreamEvent
from apix_agent.apix_agent_core.agent_factory.prompt import *
from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.apix_agent_core.context_manager.longterm_memory import longterm_memory_manager
from apix_agent.commons.type_def import MainAgentState
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.agent_factory.agent_node.agent_node_base import AgentNodeBase
from apix_agent.global_config import MAX_RETRY


class MainAgentNode(AgentNodeBase):

    def __init__(self, llm: BaseChatModel, tool_set: list[str]):
        super().__init__(llm, tool_set)


    async def context_prepare(self, state: MainAgentState) -> Command:
        """
        Call MemoryService to fetch messages in target conversation.
        Prepare sandbox, memorandum, skills, rag and memory prompt.
        Create agent message (langChain messsage object).
        """
        logger.trace('[agent.py] [AgentNode] [context_prepare] Enter')

        # Basic state extraction
        config = state.get("config", {})
        generation_id = state.get("generation_id")
        client_id = state.get("client_id")
        history_id = state.get("history_id")
        timestamp = state.get("timestamp")

        # Config flags
        work_dir = config.get("work_dir", "")
        pure_chat_on = config.get("pure_chat_on")

        enable_skill_load = config.get("enable_skill_load")
        enable_knowledge_retrieval = config.get("enable_knowledge_retrieval")
        enable_longterm_memory = config.get("enable_longterm_memory")
        enable_shortterm_memory = config.get("enable_shortterm_memory")

        keep_tools_message = config.get("keep_tools_message")

        input_msg = state["input"]
        sandbox = ""

        # Sandbox initialization
        if not state.get("sandbox"):
            sandbox = await agent_sandbox.get_sandbox_container_id(
                client_id=client_id,
                conversation_id=history_id,
                work_dir=work_dir
            )

            if not sandbox:
                sandbox = await agent_sandbox.configure_sandbox(
                    client_id=client_id,
                    conversation_id=history_id,
                    work_dir=work_dir,
                )

        # Initialize memorandum (only in agent mode)
        if not pure_chat_on:
            ai_context_manager.init_memorandum_list(state=state)

        # Load skills
        skills = []
        if not pure_chat_on and enable_skill_load:
            skills = await ai_context_manager.fetch_available_skills(client_id)

        # Load rag documents
        documents = []
        if not pure_chat_on and enable_knowledge_retrieval:
            documents = await ai_context_manager.fetch_available_documents(client_id)

        if not input_msg:
            raise RuntimeError("Error: Attempt invoke agent without input.")
        client_message = input_msg  # Only process latest message

        if client_message.get("role") == "human":
            client_message.update({
                "timestamp": timestamp,
                "generation_id": generation_id,
            })

            # Persist message and fetch full history
            await ai_context_manager.append_to_messages(client_id, history_id, client_message)
            client_messages = await ai_context_manager.fetch_messages(client_id, history_id, 0)

            # Memory processing
            longterm_memory_prompt = ""
            shortterm_memory_prompt = ""
            after_index = ""

            # Long-term memory
            if enable_longterm_memory:
                memory = await ai_context_manager.fetch_longterm_memory(client_id)
                longterm_memory_prompt = ai_context_manager.create_memory_prompt(memory)
                # Extract long-term memory from current message
                await longterm_memory_manager.submit_memory(client_id, [client_message], memory, config)

            # Short-term memory
            if enable_shortterm_memory:
                shortterm = await ai_context_manager.fetch_shortterm_memory(client_id, history_id)
                shortterm_memory_prompt = ai_context_manager.create_shortterm_prompt(shortterm)
                if shortterm:
                    after_index = shortterm[0].get("memory_id")

            # Build final messages
            messages = ai_context_manager.create_agent_messages(
                client_messages,
                keep_tools_message,
                after_index=after_index
            )

            # Return command
            return Command(
                update={
                    "messages": messages,
                    "sandbox": sandbox,
                    "skills": skills,
                    "documents": documents,
                    "longterm_memory": longterm_memory_prompt or "",
                    "shortterm_memory": shortterm_memory_prompt or "",
                }
            )
        else: raise TypeError("Unkonw role when invoke agent.")
        

    async def context_summary(self, state: MainAgentState) -> Command:
        """
        Context summary or truncate node.

        Trigger condition:
            len(messages) >= summary_trigger_threshold

        Behavior:
            enable_shortterm_memory = True
                -> summarize old messages
                -> keep last `summary_exempt_tail_length` messages

            enable_shortterm_memory = False
                -> directly truncate history
                -> keep last `summary_exempt_tail_length` messages

        Tool call boundaries are preserved via split_messages().
        """
        logger.trace('[agent.py] [AgentNode] [context_summary] Enter')

        # Config
        config = state.get("config", {})
        enable_shortterm_memory = config.get("enable_shortterm_memory")
        summary_trigger_threshold = config.get("summary_trigger_threshold")
        summary_exempt_tail_length = config.get("summary_exempt_tail_length")

        # Messages
        messages = state.get("messages", [])

        # Threshold calculation
        threshold = max(16, summary_trigger_threshold)
        keep_recent = max(8, summary_exempt_tail_length)

        # Early exit
        if len(messages) < threshold:
            return Command(update={})

        # Prevent keep_recent from being too large
        if keep_recent > threshold:
            keep_recent = threshold // 2

        logger.info(
            f"[context_summary] Trigger context control. "
            f"message_len={len(messages)} threshold={threshold}"
        )

        # Split messages
        to_process, recent_messages = ai_context_manager.split_messages(
            messages,
            keep_recent=keep_recent,
        )

        # Truncate mode (no short-term memory)
        if not enable_shortterm_memory:
            logger.success(
                "[context_summary] Truncate mode. "
                f"Reduced to {len(recent_messages)} messages."
            )

            return Command(
                update={
                    "messages": Overwrite(recent_messages),
                }
            )

        # Filter summarizable messages
        to_summarize, to_summarize_last_index = (
            ai_context_manager.filter_agent_messages(to_process)
        )

        if not to_summarize:
            return Command(update={})

        # Limit summarize size
        max_summarize_messages = summary_trigger_threshold
        to_summarize = to_summarize[-max_summarize_messages:]

        # Build summary prompt
        summary_prompt = [
            SystemMessage(content=DEFAULT_SUMMARY_PROMPT)
        ]

        # Inject existing short-term memory if exists
        if state.get("shortterm_memory"):
            summary_prompt.append(
                SystemMessage(
                    content=(
                        self.SUMMARY_MEMORY_PREFIX
                        + state["shortterm_memory"]
                    )
                )
            )

        # Add messages to summarize
        summary_prompt.extend(to_summarize)

        # Add instruction
        summary_prompt.append(HumanMessage(content=(self.SUMMARY_INSTRUCTION_PROMPT)))

        # Call LLM
        try:
            summary_msg: AIMessage = await LlmNodeAdapter.ainvoke(
                llm_node=self.llm,
                input=summary_prompt,
                reasoning=False,
            )
        except Exception as e:
            logger.error(f"[context_summary] Summary failed: {e}")
            return Command(update={})

        summary_text = summary_msg.content.strip()

        # Persist short-term memory
        await ai_context_manager.insert_shortterm_memory(
            state["client_id"],
            state["history_id"],
            to_summarize_last_index,
            summary_text
        )

        logger.success(
            "[context_summary] Summary finished. "
            f"Reduced to {len(recent_messages)} messages."
        )

        # Return result
        return Command(
            update={
                "messages": Overwrite(recent_messages),
                "shortterm_memory": summary_text
            }
        )
    

    async def llm_call(self, state: MainAgentState) -> Command:
        """
        Merge system prompt and context.
        Call LLM with current conversation state.
        """
        logger.trace('[agent.py] [AI_Agent] [llm_call] Enter')

        # Basic config
        agent_role = state.get("agent_role")
        client_id = state.get("client_id")
        target_platform = state.get("platform")
        config = state.get("config", {})
        llm_calls_warning_threshold = config.get("llm_calls_warning_threshold")
        summary_exempt_tail_length = config.get("summary_exempt_tail_length")

        pure_chat_on = config.get("pure_chat_on")
        enable_think = config.get("enable_think")

        enable_skill_load = config.get("enable_skill_load")
        enable_knowledge_retrieval = config.get("enable_knowledge_retrieval")

        # Runtime
        event_writer = ApixStreamWriter()
        messages = state["messages"]

        logger.info(
            f'[agent.py] [AI_Agent] [llm_call] Invoke llm with {len(messages)} messages'
        )

        # Load base rule prompt
        state["rule_prompt"] = self._load_prompt(agent_role)

        # Build runtime prompt (workspace + extensions)
        workspace_prompt = ai_context_manager.create_workspace_prompt(state, agent_role)
        runtime_prompt_parts = [workspace_prompt]

        if not pure_chat_on:
            # Skills
            if enable_skill_load:
                runtime_prompt_parts.append(
                    ai_context_manager.create_skills_prompt(state, agent_role)
                )

            # Documents
            if enable_knowledge_retrieval:
                runtime_prompt_parts.append(
                    ai_context_manager.create_documents_prompt(state, agent_role)
                )

            # Memorandum
            runtime_prompt_parts.append(
                ai_context_manager.create_memorandum_prompt(state, agent_role)
            )

            # TodoItems
            todo_prompt = ai_context_manager.create_todo_prompt(state, agent_role)
            runtime_prompt_parts.append(todo_prompt)

            logger.info(
                f'[agent.py] [AI_Agent] [llm_call] Load todos:\n {todo_prompt}'
            )

        # Merge all runtime prompt parts
        runtime_prompt = "".join(runtime_prompt_parts)
        state["runtime_prompt"] = runtime_prompt

        # Build final LLM input
        system_prompt = ai_context_manager.create_system_prompt_list(state, agent_role)
        role_prompt = ai_context_manager.create_role_prompt_list(state, agent_role)

        llm_input = system_prompt + role_prompt + messages

        # Inject alert if necessary
        need_alert = self._should_inject_alert(
            llm_calls=state.get("llm_calls", 0),
            llm_calls_warning_threshold=llm_calls_warning_threshold,
            summary_exempt_tail_length=summary_exempt_tail_length,
        )
        if need_alert:
            llm_input = llm_input + [SystemMessage(self.SYSTEM_ALERT_PROMPT)]

        # Start streaming
        chunk_iterator = LlmNodeAdapter.astream(
            llm_node=self.llm,
            input=llm_input,
            reasoning=enable_think,
        )

        event_writer.send_event(
            event=StreamEvent.LLM_STREAM_START, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "node_stream_start",
                "content": "[Start LLM Response (single node)]"
            }
        )

        ai_msg_chunk = AIMessageChunk(content="")

        # Stream loop
        try:
            async for chunk in chunk_iterator:
                print('.', end="")  # debug output

                ai_msg_chunk = ai_msg_chunk + chunk

                # Extract fields safely
                think = (
                    chunk.additional_kwargs.get('reasoning_content')
                    if chunk.additional_kwargs else None
                )
                content = chunk.text
                tool_calls = chunk.tool_calls

                # Streaming output
                if think:
                    event_writer.send_event(
                        event=StreamEvent.LLM_CHUNK_RETURN, 
                        target_id=client_id, 
                        target_platform=target_platform,
                        data={
                            "event_name": "think_chunk_rtn",
                            "content": think
                        }
                    )
                elif content:
                    event_writer.send_event(
                        event=StreamEvent.LLM_CHUNK_RETURN, 
                        target_id=client_id, 
                        target_platform=target_platform,
                        data={
                            "event_name": "content_chunk_rtn",
                            "content": content
                        }
                    )
                if tool_calls:
                    event_writer.send_event(
                        event=StreamEvent.LLM_CHUNK_RETURN, 
                        target_id=client_id, 
                        target_platform=target_platform,
                        data={
                            "event_name": "tool_chunk_rtn",
                            "content": tool_calls
                        }
                    )

        except Exception as e:
            retry_count = state.get("retry_count", 0) + 1
            logger.warning(f"[llm_call] Error occurred: {type(e).__name__}; \nRetry at soon ({retry_count}/3)...")
            await asyncio.sleep(1)
            if retry_count <= MAX_RETRY:
                return Command(
                    update={
                        "retry_count": retry_count
                    },
                    goto='llm_call'
                )
            else:
                raise e


        print('\n')

        # End streaming
        event_writer.send_event(
            event=StreamEvent.LLM_STREAM_END, 
            target_id=client_id, 
            target_platform=target_platform,
            data={
                "event_name": "node_stream_end",
                "content": "[Finish LLM Response] (single node)"
            }
        )
        
        delta_msg = [ai_msg_chunk]
        # Build final message
        if need_alert:
            delta_msg = [
                SystemMessage(self.SYSTEM_ALERT_PROMPT),
                ai_msg_chunk
            ]

        return Command(
            update={
                "messages": delta_msg,
                "llm_calls": 1,
                "retry_count": 0
            }
        )
    
    
    async def messages_persist(self, state: MainAgentState) -> Command:
        """
        Call MemoryService to store messages in target conversation.

        Special handling:
        - AIMessage may contain tool_calls -> update current_tool_calls
        - ToolMessage comes in batch (size == tool_calls) -> persist all together
        """
        messages = state.get("messages", [])
        if not messages:
            return Command(update={})
        last_message = messages[-1]

        generation_id = state.get("generation_id")
        client_id = state.get("client_id")
        target_platform = state.get("platform")
        history_id = state.get("history_id")
        timestamp = state.get("timestamp")

        config = state.get("config")
        model_name = config.get("model_name")
        model_provider = config.get("models_provider")

        event_writer = ApixStreamWriter()

        current_tool_calls = []

        # Case 1: AIMessage (may contain tool calls)
        if isinstance(last_message, (AIMessage, AIMessageChunk)):
            if last_message.tool_calls:
                current_tool_calls = last_message.tool_calls

            # Persist single AI message
            client_message = ai_context_manager.create_dict_message(
                generation_id,
                last_message,
                timestamp,
                fallback_model_name=model_name,
                fallback_model_provider=model_provider,
                fallback_timestamp=timestamp
            )
            await ai_context_manager.append_to_messages(
                client_id, history_id, client_message
            )
            
            event_writer.send_event(
                event=StreamEvent.LLM_STREAM_END, 
                target_id=client_id, 
                target_platform=target_platform,
                data={
                    "event_name": "messages_persist_end",
                    "content": ""
                }
            )

            return Command(
                update={
                    "current_tool_calls": current_tool_calls,
                }
            )

        # Case 2: ToolMessage (batch return from ToolNode)
        elif isinstance(last_message, ToolMessage):
            tool_calls = state.get("current_tool_calls", [])
            tool_call_ids = {call["id"] for call in tool_calls}

            tool_msg_list = [
                msg for msg in messages
                if isinstance(msg, ToolMessage) and msg.tool_call_id in tool_call_ids
            ]

            # Persist all tool messages in batch
            for msg in tool_msg_list:
                tool_message = ai_context_manager.create_dict_message(
                    generation_id,
                    msg,
                    timestamp,
                    fallback_model_name=model_name,
                    fallback_model_provider=model_provider,
                    fallback_timestamp=timestamp
                )
                await ai_context_manager.append_to_messages(
                    client_id, history_id, tool_message
                )
            
            event_writer.send_event(
                event=StreamEvent.LLM_STREAM_END, 
                target_id=client_id, 
                target_platform=target_platform,
                data={
                    "event_name": "messages_persist_end",
                    "content": ""
                }
            )

            return Command(
                update={
                    "current_tool_calls": []
                }
            )

        # Case 3: Other message types (Human/System/etc.)
        else:
            client_message = ai_context_manager.create_dict_message(
                generation_id,
                last_message,
                timestamp,
                fallback_model_name=model_name,
                fallback_model_provider=model_provider,
                fallback_timestamp=timestamp
            )

            await ai_context_manager.append_to_messages(
                client_id, history_id, client_message
            )
            
            event_writer.send_event(
                event=StreamEvent.LLM_STREAM_END, 
                target_id=client_id, 
                target_platform=target_platform,
                data={
                    "event_name": "messages_persist_end",
                    "content": ""
                }
            )

            return Command(
                update={
                    "current_tool_calls": current_tool_calls
                }
            )
