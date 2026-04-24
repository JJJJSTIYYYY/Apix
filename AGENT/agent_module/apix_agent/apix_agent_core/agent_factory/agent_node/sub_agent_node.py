from uuid import uuid4

from openai import BadRequestError, RateLimitError

from langchain.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessageChunk, HumanMessage, ToolMessage, AIMessage
from langgraph.graph import END
from langgraph.graph.state import Command
from langgraph.types import Overwrite
from langgraph.config import get_stream_writer

from apix_agent.apix_event_pipe.stream_writer import ApixStreamWriter, StreamEvent
from apix_agent.apix_agent_core.agent_factory.prompt import *
from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.apix_agent_core.context_manager.generating_cache import generating_cache
from apix_agent.commons.type_def import SubAgentState
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.agent_factory.agent_node.agent_node_base import AgentNodeBase
from apix_agent.global_config import MAX_RETRY


class SubAgentNode(AgentNodeBase):

    def __init__(self, llm: BaseChatModel, tool_set: list[str]):
        super().__init__(llm, tool_set)
    
    async def _refresh_team_worker_history(
        self,
        *,
        state: SubAgentState,
        recent_messages,
        summary_text: str | None = None
    ):
        """Rewrite team worker history (optionally with summary)."""
        try:
            history_id = state.get("history_id")
            agent_name = state.get("agent_name")
            generation_id = state.get("generation_id")
            timestamp = state.get("timestamp")

            new_history = []

            if summary_text:
                new_history.append({
                    "role": "system",
                    "content": summary_text,
                    "timestamp": timestamp,
                    "generation_id": generation_id
                })

            for msg in recent_messages:
                if isinstance(msg, dict):
                    new_history.append(msg)
                else:
                    msg_dict = ai_context_manager.create_dict_message(
                        generation_id,
                        msg,
                        timestamp,
                        filter=True
                    )
                    if msg_dict:
                        new_history.append(msg_dict)

            await generating_cache.rewrite_history(
                history_id=history_id,
                agent_name=agent_name,
                messages=new_history
            )

        except Exception as e:
            logger.error(f"[context_summary] rewrite sub-agent history failed: {e}")


    async def context_prepare(self, state: SubAgentState) -> Command:
        """
        Call MemoryService to fetch messages in target conversation.
        Fetch and update longterm memory if allowed.
        """
        task_id = state.get("task_id") or str(uuid4())

        # Basic state extraction
        agent_role = state.get("agent_role")
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
        client_message = input_msg # Fetch the latest one only.

        if client_message.get("role") == "human":
            client_message.update({
                "timestamp": timestamp,
                "generation_id": generation_id,
            })
            if agent_role == "team_worker":
                await generating_cache.append_dict_message(
                    history_id=history_id,
                    agent_name=state.get("agent_name"),
                    message_dict=client_message
                )

                history_messages = await generating_cache.load_history(
                    history_id=history_id,
                    agent_name=state.get("agent_name"),
                )

                client_messages = history_messages
            else:
                client_messages = [client_message]

            messages = ai_context_manager.create_agent_messages(client_messages, keep_tools_message)
            return Command(
                update={
                    "messages": messages,
                    "sandbox": sandbox,
                    "skills": skills,
                    "documents": documents,
                    "task_id": task_id,
                }
            )
        else:
            raise TypeError("Unknown role when invoke sub-agent.")
        

    # async def _context_summary(self, state: SubAgentState) -> Command:
    #     """
    #     Context summary or truncate node.

    #     Trigger condition:
    #         len(messages) >= summary_trigger_threshold

    #     Behavior:
    #         enable_shortterm_memory = True
    #             -> summarize old messages
    #             -> keep last `summary_exempt_tail_length` messages

    #         enable_shortterm_memory = False
    #             -> directly truncate history
    #             -> keep last `summary_exempt_tail_length` messages

    #     Tool call boundaries are preserved via split_messages().
    #     """
    #     # Config
    #     agent_role = state.get("agent_role")
    #     config = state.get("config", {})
    #     enable_shortterm_memory = config.get("enable_shortterm_memory")
    #     summary_trigger_threshold = config.get("summary_trigger_threshold")
    #     summary_exempt_tail_length = config.get("summary_exempt_tail_length")

    #     # Messages
    #     messages = state.get("messages", [])

    #     # Threshold calculation
    #     threshold = max(16, summary_trigger_threshold)
    #     keep_recent = max(8, summary_exempt_tail_length)

    #     # Early exit
    #     if len(messages) < threshold:
    #         return Command(update={})

    #     # Prevent keep_recent from being too large
    #     if keep_recent > threshold:
    #         keep_recent = threshold // 2

    #     to_process, recent_messages = ai_context_manager.split_messages(
    #         messages,
    #         keep_recent=keep_recent,
    #     )

    #     # Truncate mode (no short-term memory)
    #     if not enable_shortterm_memory:
    #         if agent_role == "team_worker": # Refresh team worker's message context
    #             await self._refresh_team_worker_history(
    #                 state=state,
    #                 recent_messages=recent_messages
    #             )

    #         return Command(
    #             update={
    #                 "messages": Overwrite(recent_messages),
    #             }
    #         )

    #     # Filter summarizable messages
    #     sys_msgs, to_summarize, to_summarize_last_index = (
    #         ai_context_manager.filter_agent_messages(to_process)
    #     )

    #     if not to_summarize:
    #         return Command(update={})

    #     # Limit summarize size
    #     max_summarize_messages = summary_trigger_threshold
    #     to_summarize = to_summarize[-max_summarize_messages:]

    #     # Build summary prompt
    #     summary_prompt = [
    #         SystemMessage(content=DEFAULT_SUMMARY_PROMPT)
    #     ]

    #     # Inject existing short-term memory if exists
    #     if state.get("shortterm_memory"):
    #         summary_prompt.append(
    #             SystemMessage(
    #                 content=(
    #                     self.SUMMARY_MEMORY_PREFIX
    #                     + state["shortterm_memory"]
    #                 )
    #             )
    #         )

    #     # Add messages to summarize
    #     summary_prompt.extend(to_summarize)

    #     # Add instruction
    #     summary_prompt.append(HumanMessage(content=(self.SUMMARY_INSTRUCTION_PROMPT)))

    #     # Call LLM
    #     try:
    #         summary_msg: AIMessage = await LlmNodeAdapter.ainvoke(
    #             llm_node=self.llm,
    #             input=summary_prompt,
    #             reasoning=False,
    #         )
    #     except Exception as e:
    #         logger.error(f"[context_summary] Summary failed: {e}")
    #         return Command(update={})

    #     summary_text = summary_msg.content.strip()

    #     # Persist short-term memory
    #     if agent_role == "team_worker":
    #         await self._refresh_team_worker_history(
    #             state=state,
    #             recent_messages=recent_messages,
    #             summary_text=summary_text
    #         )

    #     # Return result
    #     return Command(
    #         update={
    #             "messages": Overwrite(recent_messages),
    #             "shortterm_memory": summary_text
    #         }
    #     )
    
    
    async def context_summary(self, state: SubAgentState) -> Command:
        """
        Context compression node (multi-level).

        Trigger:
            1. len(messages) >= threshold
            2. OR retry caused by token_exceed

        Compression levels:
            0: no-op
            1: drop_tool_messages (light, reversible)
            2: LLM summary (lossy)
            3: drop_tool_messages(min_keep=2)
            4+: exponential truncate (reversible)
        """
        logger.trace('[agent.py] [AgentNode] [context_summary] Enter')

        # Config
        agent_role = state.get("agent_role")
        config = state.get("config", {})
        enable_shortterm_memory = config.get("enable_shortterm_memory")
        summary_trigger_threshold = config.get("summary_trigger_threshold")
        summary_exempt_tail_length = config.get("summary_exempt_tail_length")

        # State
        llm_retry_count = state.get("llm_retry_count", 0)
        last_error = state.get("error", "")
        context_compress_level = state.get("context_compress_level", 0)
        shortterm_memory = state.get("shortterm_memory", "")

        messages = state.get("messages", [])

        # Threshold
        threshold = max(16, summary_trigger_threshold)
        keep_recent_base = max(8, summary_exempt_tail_length)

        # Trigger condition
        should_trigger = (
            len(messages) >= threshold
            or (llm_retry_count > 0 and last_error == "token_exceed")
        )

        # if len(messages) >= threshold:
        #     context_compress_level = max(context_compress_level, 2)

        if not should_trigger:
            return Command(update={})

        logger.info(
            f"[context_summary] Triggered. "
            f"len={len(messages)} level={context_compress_level} "
            f"retry={llm_retry_count} error={last_error}"
        )

        # Helper: exponential keep
        def calc_keep(level: int) -> int:
            # exponential backoff: keep shrinks as level increases
            keep = keep_recent_base // (2 ** max(1, level - 3))
            return max(2, keep)

        # Case 1: shortterm memory disabled: always truncate
        if not enable_shortterm_memory:
            keep_recent = calc_keep(context_compress_level)

            _, recent_messages = ai_context_manager.split_messages(
                messages,
                keep_recent=keep_recent,
            )

            if agent_role == "team_worker": # Refresh team worker's message context
                await self._refresh_team_worker_history(
                    state=state,
                    recent_messages=recent_messages
                )

            logger.success(
                f"[context_summary] Truncate (memory disabled). keep={keep_recent}"
            )

            return Command(
                update={
                    "messages": Overwrite(recent_messages),
                }
            )

        # Case 2: Level-based compression

        # Level 0: no-op
        if context_compress_level <= 0:
            return Command(update={})

        # Level 1: drop tool messages
        if context_compress_level == 1:
            new_messages = ai_context_manager.drop_tool_messages(
                messages,
                split_by_todos=True,
                min_keep=keep_recent_base,
            )

            logger.success(
                f"[context_summary] Level1 drop_tool_messages "
                f"(min_keep={keep_recent_base})"
            )

            return Command(
                update={
                    "messages": Overwrite(new_messages),
                }
            )

        # Level 2: LLM summary, this will commit to database and can not roll back
        if context_compress_level == 2:
            # Split messages (preserve tool boundary)
            to_process, recent_messages = ai_context_manager.split_messages(
                messages,
                keep_recent=keep_recent_base,
            )

            # Filter summarizable messages
            sys_msgs, to_summarize, to_summarize_last_index = (
                ai_context_manager.filter_agent_messages(to_process)
            )

            # Nothing to summarize: go to level 3 in next loop
            if not to_summarize:
                return Command(update={})

            # Limit summarize size
            max_summarize_messages = summary_trigger_threshold
            to_summarize = to_summarize[-max_summarize_messages:]

            # Build prompt
            summary_prompt = [
                SystemMessage(content=DEFAULT_SUMMARY_PROMPT)
            ]

            if shortterm_memory:
                summary_prompt.append(
                    HumanMessage(
                        content=self.SUMMARY_MEMORY_PREFIX + shortterm_memory
                    )
                )

            summary_prompt.extend(to_summarize)
            summary_prompt.append(
                HumanMessage(content=self.SUMMARY_INSTRUCTION_PROMPT)
            )

            # Call LLM
            try:
                summary_msg: AIMessage = await LlmNodeAdapter.ainvoke(
                    llm_node=self.llm,
                    input=summary_prompt,
                    reasoning=False,
                )
            except Exception as e:
                logger.error(f"[context_summary] Summary failed: {e}")
                # Directly entry next level
                return Command(update={})

            summary_text = summary_msg.content.strip()

            # Persist short-term memory
            if agent_role == "team_worker":
                await self._refresh_team_worker_history(
                    state=state,
                    recent_messages=recent_messages,
                    summary_text=summary_text
                )

            logger.success(
                f"[context_summary] Level2 summary done. "
                f"remain={len(recent_messages)}"
            )

            return Command(
                update={
                    "messages": Overwrite(sys_msgs+recent_messages),
                    "shortterm_memory": summary_text
                }
            )

        # Level 3: aggressive drop tool messages
        if context_compress_level == 3:
            new_messages = ai_context_manager.drop_tool_messages(
                messages,
                split_by_todos=True,
                min_keep=2,
            )

            logger.success("[context_summary] Level 3 drop_tool_messages(min_keep=2)")

            return Command(
                update={
                    "messages": Overwrite(new_messages),
                }
            )

        # Level >=4: exponential truncate
        keep_recent = calc_keep(context_compress_level)

        _, recent_messages = ai_context_manager.split_messages(
            messages,
            keep_recent=keep_recent,
        )

        logger.success(
            f"[context_summary] Level{context_compress_level} truncate "
            f"(keep={keep_recent})"
        )

        return Command(
            update={
                "messages": Overwrite(recent_messages),
            }
        )
    

    async def llm_call(self, state: SubAgentState) -> Command:
        """
        Merge system prompt and context.
        Call LLM with current conversation state.
        """
        # Basic config
        agent_role = state.get("agent_role")
        config = state.get("config", {})
        llm_calls_warning_threshold = config.get("llm_calls_warning_threshold")
        summary_exempt_tail_length = config.get("summary_exempt_tail_length")

        pure_chat_on = config.get("pure_chat_on")
        enable_think = config.get("enable_think")

        enable_skill_load = config.get("enable_skill_load")
        enable_knowledge_retrieval = config.get("enable_knowledge_retrieval")
        loaded_skills_cache = state.get("loaded_skills_cache")

        # Runtime
        messages = state["messages"]

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

        # Merge all runtime prompt parts
        runtime_prompt = "".join(runtime_prompt_parts)
        state["runtime_prompt"] = runtime_prompt

        # Build final LLM input
        system_prompt = ai_context_manager.create_system_prompt_list(state, agent_role)
        role_prompt = ai_context_manager.create_role_prompt_list(state, agent_role)

        llm_input = system_prompt + role_prompt + messages
                
        # Inject the skill markdown (only those not injected yet)
        new_skills_cache = []
        if enable_skill_load and loaded_skills_cache:
            skill_msgs = []

            for name, injected, guide in loaded_skills_cache:
                if not injected:
                    skill_msgs.append(
                        SystemMessage(
                            content=f"# [Detail Guide for Skill `{name}`]\n\n{guide}"
                        )
                    )
                    # Mark as injected
                    new_skills_cache.append((name, True, guide))
                else:
                    new_skills_cache.append((name, injected, guide))

            # Inject
            if skill_msgs and state.get("llm_calls", 0) > 0:
                llm_input = llm_input + skill_msgs
            elif skill_msgs and state.get("llm_calls", 0) == 0:
                llm_input = system_prompt + role_prompt + skill_msgs + messages

        # Inject alert if necessary
        need_alert = self._should_inject_alert(
            llm_calls=state.get("llm_calls", 0),
            threshold=llm_calls_warning_threshold,
        )
        if need_alert:
            llm_input = llm_input + [SystemMessage(self.SYSTEM_ALERT_PROMPT)]

        # Start streaming
        chunk_iterator = LlmNodeAdapter.astream(
            llm_node=self.llm,
            input=llm_input,
            reasoning=enable_think,
        )

        # Stream loop
        try:
            ai_msg_chunk = AIMessageChunk(content="")
            async for chunk in chunk_iterator:
                ai_msg_chunk = ai_msg_chunk + chunk

        except BadRequestError as e:
            llm_retry_count = state.get("llm_retry_count", 0) + 1
            context_compress_level = state.get("context_compress_level", 0) + 1
            logger.warning(f"[llm_call] Error occurred: {type(e).__name__}; \nRetry at soon ({llm_retry_count}/{MAX_RETRY})...")
            if llm_retry_count < MAX_RETRY and  LlmNodeAdapter.guess_exception_type(str(e)) == 'token_exceed':
                return Command(
                    update={
                        "llm_retry_count": llm_retry_count,
                        "error": "token_exceed",
                        "context_compress_level": context_compress_level
                    },
                )
            else:
                raise e
            
        except RateLimitError as e:
            llm_retry_count = state.get("llm_retry_count", 0) + 1
            logger.warning(f"[llm_call] Error occurred: {type(e).__name__}; \nRetry at soon ({llm_retry_count}/{MAX_RETRY})...")
            if llm_retry_count < MAX_RETRY and  LlmNodeAdapter.guess_exception_type(str(e)) == 'rate_limit':
                return Command(
                    update={
                        "llm_retry_count": llm_retry_count,
                        "error": "rate_limit"
                    },
                )
            else:
                raise e
        
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
                "llm_retry_count": 0,
                "context_compress_level": 0 if state.get("context_compress_level", 0) <= 2 else 3,
                "error": "",
                "loaded_skills_cache": new_skills_cache,
            }
        )
    
    
    async def messages_persist(self, state: SubAgentState) -> Command:
        """
        Store messages to file system as log.

        Special handling:
        - AIMessage may contain tool_calls -> update current_tool_calls
        - ToolMessage comes in batch (size == tool_calls) -> persist all together
        """
        messages = state.get("messages", [])
        if not messages:
            return Command(update={})
        last_message = messages[-1]

        agent_role = state.get("agent_role")
        agent_name = state.get("agent_name")
        task_id = state.get("task_id")
        generation_id = state.get("generation_id")
        client_id = state.get("client_id")
        target_platform = state.get("platform")
        history_id = state.get("history_id")
        timestamp = state.get("timestamp")

        config = state.get("config")
        model_name = config.get("model_name")
        model_provider = config.get("models_provider")

        current_tool_calls = []
        event_writer = ApixStreamWriter()

        # Case 1: AIMessage (may contain tool calls)
        if isinstance(last_message, (AIMessage, AIMessageChunk)):
            if last_message.tool_calls:
                current_tool_calls = last_message.tool_calls
                
            # Yield delta content output
            delta_outputs = last_message.content or ""
            event_writer.send_event(
                event=StreamEvent.AI_MESSAGE_RETURN, 
                target_id=client_id, 
                target_platform=target_platform,
                data={
                    "event_name": "output_chunk_rtn",
                    "content": state["outputs"] + delta_outputs
                }
            )

            # Persist single AI message for team worker
            if agent_role == "team_worker":
                client_message = ai_context_manager.create_dict_message(
                    generation_id,
                    last_message,
                    timestamp,
                    filter=True,
                    fallback_model_name=model_name,
                    fallback_model_provider=model_provider,
                    fallback_timestamp=timestamp
                )
                await generating_cache.append_dict_message(
                    history_id=history_id,
                    agent_name=agent_name,
                    message_dict=client_message
                )

            return Command(
                update={
                    "current_tool_calls": current_tool_calls,
                    "outputs": delta_outputs
                }
            )

        # Case 2: ToolMessage (batch return from ToolNode)
        if isinstance(last_message, ToolMessage):
            tool_calls = state.get("current_tool_calls", [])
            tool_call_ids = {call["id"] for call in tool_calls}

            # Step 1: filter relevant ToolMessage
            tool_msg_list = [
                msg for msg in messages
                if isinstance(msg, ToolMessage) and msg.tool_call_id in tool_call_ids
            ]

            # Step 2: deduplicate by tool_call_id (keep latest)
            dedup_map = {}
            for msg in tool_msg_list:
                # overwrite to ensure we keep the last occurrence
                dedup_map[msg.tool_call_id] = msg

            deduped_tool_msgs = list(dedup_map.values())

            # Persist all tool messages in batch
            for msg in deduped_tool_msgs:
                tool_message = ai_context_manager.create_dict_message(
                    generation_id,
                    msg,
                    timestamp,
                    filter=True,
                    fallback_model_name=model_name,
                    fallback_model_provider=model_provider,
                    fallback_timestamp=timestamp
                )
                # Write tool calls log
                await logger.write_log("sub_agent_logs", task_id, tool_message)

                # Persist tool message for team worker
                if agent_role == "team_worker":
                    await generating_cache.append_dict_message(
                        history_id=history_id,
                        agent_name=agent_name,
                        message_dict=tool_message
                    )

            return Command(
                update={
                    "current_tool_calls": []
                }
            )
        
        # Case 3: Other message types (Human/System/etc.), only persist for team worker
        elif agent_role == "team_worker":
            client_message = ai_context_manager.create_dict_message(
                generation_id,
                last_message,
                timestamp,
                filter=True,
                fallback_model_name=model_name,
                fallback_model_provider=model_provider,
                fallback_timestamp=timestamp
            )

            await generating_cache.append_dict_message(
                history_id=history_id,
                agent_name=agent_name,
                message_dict=client_message
            )

            return Command(
                update={
                    "current_tool_calls": current_tool_calls
                }
            )

        return Command(update={})
