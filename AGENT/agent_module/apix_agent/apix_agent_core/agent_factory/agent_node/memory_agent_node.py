from openai import BadRequestError, RateLimitError

from langchain.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, AIMessageChunk, HumanMessage, ToolMessage, AIMessage
from langgraph.graph.state import Command
from langgraph.types import Overwrite

from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.apix_agent_core.agent_factory.prompt import *
from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.apix_agent_core.context_manager.longterm_memory import longterm_memory_manager
from apix_agent.commons.type_def import InvalidOutputsError, MainAgentState, ConflictToolCalls
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
        re_generate = state.get("re_generate")

        # Config flags
        enable_think = config.get("enable_think", False)
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
            if not re_generate: 
                # For a full generation wtih new user input.
                await ai_context_manager.append_to_messages(client_id, history_id, client_message)
                # A new uer message appended in database, update the last confirmed node_id to this message
                current_visible_node_id = generation_id + '-user'
            else: 
                # For a incomplete generation wtihout user input. (re-generation mode)
                # parent_id in client_message means the last confirmed node_id
                current_visible_node_id = client_message.get("parent_id", '-')
            # Ensure agent message node's parent_id in this generation (normally equals to current_visible_node_id)
            client_messages, parent_id = await ai_context_manager.fetch_messages(client_id, history_id, 0, current_visible_node_id)

            event_writer = AgentStreamWriter(generation_id)
            target = state.get("target")
            event_writer.send_event(
                event=AgentStreamEvent.ESSENTIAL_INFO_RETURN,
                target=target,
                data={
                    "event_name": "parent_id_return",
                    "content": parent_id or '-'
                }
            )

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
                after_index=after_index,
                reasoning=enable_think
            )
            logger.info(f"[context_prepare] Prepared message objects: {messages}")

            # Return command
            return Command(
                update={
                    "messages": messages,
                    "sandbox": sandbox,
                    "skills": skills,
                    "documents": documents,
                    "longterm_memory": longterm_memory_prompt or "",
                    "shortterm_memory": shortterm_memory_prompt or "",
                    "parent_node_id": parent_id or "-",
                }
            )
        else: raise TypeError("Unkonw role when invoke agent.")
    

    async def context_summary(self, state: MainAgentState) -> Command:
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
        generation_id = state.get("generation_id")
        config = state.get("config", {})
        enable_shortterm_memory = config.get("enable_shortterm_memory")
        summary_trigger_threshold = config.get("summary_trigger_threshold")
        summary_exempt_tail_length = config.get("summary_exempt_tail_length")

        # State
        llm_retry_count = state.get("llm_retry_count", 0)
        last_error = state.get("error", "")
        context_compress_level = state.get("context_compress_level", 0)
        shortterm_memory = state.get("shortterm_memory", "")

        logger.info(f"[context_summary] Existing shortterm memory:\n{shortterm_memory}")

        messages = state.get("messages", [])

        # Threshold
        threshold = max(16, summary_trigger_threshold)
        keep_recent_base = max(8, summary_exempt_tail_length)

        # Trigger condition
        should_trigger = (
            len(messages) >= threshold
            or (llm_retry_count > 0 and last_error == "token_exceed")
        )

        if len(messages) >= threshold:
            context_compress_level = max(context_compress_level, 2)

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
                    reasoning=True,
                    fall_back_config=config
                )
            except Exception as e:
                logger.error(f"[context_summary] Summary failed: {e}")
                # Directly entry next level
                return Command(update={})

            summary_text = summary_msg.content.strip()

            # Persist memory
            await ai_context_manager.insert_shortterm_memory(
                state["client_id"],
                state["history_id"],
                to_summarize_last_index,
                summary_text
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

        event_writer = AgentStreamWriter(generation_id)
        target = state.get("target")
        event_writer.send_event(
            event=AgentStreamEvent.RUNTIME_WARNING,
            target=target,
            data={
                "event_name": "token_limit_warning",
                "content": "The currently selected model is too small to load the full context."
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


    async def llm_call(self, state: MainAgentState) -> Command:
        """
        Merge system prompt and context.
        Call LLM with current conversation state.
        """
        logger.trace('[agent.py] [AI_Agent] [llm_call] Enter')

        # Basic config
        agent_role = state.get("agent_role")
        client_id = state.get("client_id")
        target = state.get("target")
        generation_id = state.get("generation_id")
        config = state.get("config", {})
        llm_calls_warning_threshold = config.get("llm_calls_warning_threshold")

        pure_chat_on = config.get("pure_chat_on")
        enable_think = config.get("enable_think")

        enable_skill_load = config.get("enable_skill_load")
        enable_knowledge_retrieval = config.get("enable_knowledge_retrieval")
        loaded_skills_cache = state.get("loaded_skills_cache")

        # Runtime
        event_writer = AgentStreamWriter(generation_id)
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
                
        # Inject the skill markdown (only those not injected yet)
        new_skills_cache = []
        if enable_skill_load and loaded_skills_cache:
            skill_msgs = []
            char_num = 0

            for name, injected, guide in loaded_skills_cache:
                if not injected:
                    skill_msgs.append(
                        SystemMessage(
                            content=f"# [SKILL.md from the loaded skill package: `{name}`]\n\n{guide}"
                        )
                    )
                    # Mark as injected
                    new_skills_cache.append((name, True, guide))
                    char_num = char_num + len(skill_msgs[-1].content)
                else:
                    new_skills_cache.append((name, injected, guide))

            if skill_msgs:
                # Inject
                llm_input = llm_input + skill_msgs
                logger.warning(f"[agent.py] [AI_Agent] [llm_call] Injected {len(skill_msgs)} skill(s) markdown. [{char_num} Chars]")

        # Inject alert if necessary
        need_alert = self._should_inject_alert(
            llm_calls=state.get("llm_calls", 0),
            threshold=llm_calls_warning_threshold,
        )
        if need_alert:
            logger.warning(f"[agent.py] [AI_Agent] [llm_call] Inject `SYSTEM_ALERT_PROMPT`: {self.SYSTEM_ALERT_PROMPT}")
            llm_input = llm_input + [SystemMessage(self.SYSTEM_ALERT_PROMPT)]
        if state.get("error_detail"):
            logger.warning(f"[agent.py] [AI_Agent] [llm_call] Inject `CRITICAL WARN`: {state.get("error_detail")}")
            llm_input = llm_input + [SystemMessage(f"CRITICAL WARN: {state.get("error_detail")}. If you are trying to do that, stop immediately any way!")]

        # Start streaming
        chunk_iterator = LlmNodeAdapter.astream(
            llm_node=self.llm,
            input=llm_input,
            reasoning=enable_think,
            fall_back_config=config
        )

        event_writer.send_event(
            event=AgentStreamEvent.LLM_STREAM_START, 
            target=target,
            data={
                "event_name": "node_stream_start",
                "content": "[Start LLM Response (single node)]"
            }
        )

        ai_msg_chunk = AIMessageChunk(content="")
        chunk_num = 0

        # Stream loop
        try:
            async for chunk in chunk_iterator:
                chunk_num = chunk_num + 1
                ai_msg_chunk = ai_msg_chunk + chunk

                # Extract fields safely
                think = (
                    chunk.additional_kwargs.get('reasoning_content')
                    if chunk.additional_kwargs else None
                )
                content = chunk.text
                tool_calls = chunk.tool_calls or chunk.tool_call_chunks

                # Streaming output
                if think:
                    event_writer.send_event(
                        event=AgentStreamEvent.LLM_CHUNK_RETURN, 
                        target=target,
                        data={
                            "event_name": "think_chunk_rtn",
                            "content": think
                        }
                    )
                elif content:
                    event_writer.send_event(
                        event=AgentStreamEvent.LLM_CHUNK_RETURN, 
                        target=target,
                        data={
                            "event_name": "content_chunk_rtn",
                            "content": content
                        }
                    )
                if tool_calls:
                    event_writer.send_event(
                        event=AgentStreamEvent.LLM_CHUNK_RETURN, 
                        target=target,
                        data={
                            "event_name": "tool_chunk_rtn",
                            "content": tool_calls
                        }
                    )
            
            ai_msg_chunk = self._ensure_agent_message(ai_msg_chunk, reasoning=enable_think)

        except ConflictToolCalls as e:
            llm_retry_count = state.get("llm_retry_count", 0) + 1
            logger.warning(f"[llm_call] Error occurred: {type(e).__name__}; \nRetry at soon ({llm_retry_count}/{MAX_RETRY})...")
            event_writer.send_event(
                event=AgentStreamEvent.RUNTIME_WARNING, 
                target=target,
                data={
                    "event_name": "conflict_tool_calls_warning",
                    "content": {
                        "tool_name": " ".join(e.errors),
                        "retry": llm_retry_count
                    }
                }
            )
            if llm_retry_count < MAX_RETRY:
                return Command(
                    update={
                        "llm_retry_count": llm_retry_count,
                        "error": "others",
                        "error_detail": e.message
                    },
                )
            else:
                raise e

        except InvalidOutputsError as e:
            llm_retry_count = state.get("llm_retry_count", 0) + 1
            logger.warning(f"[llm_call] Error occurred: {type(e).__name__}; \nRetry at soon ({llm_retry_count}/{MAX_RETRY})...")
            event_writer.send_event(
                event=AgentStreamEvent.RUNTIME_WARNING, 
                target=target,
                data={
                    "event_name": "invalid_outputs_warning",
                    "content": {
                        "retry": llm_retry_count
                    }
                }
            )
            if llm_retry_count < MAX_RETRY:
                return Command(
                    update={
                        "llm_retry_count": llm_retry_count,
                        "error": "others"
                    },
                )
            else:
                raise e

        except BadRequestError as e:
            llm_retry_count = state.get("llm_retry_count", 0) + 1
            context_compress_level = state.get("context_compress_level", 0) + 1
            logger.warning(f"[llm_call] Error occurred: {type(e).__name__}; \nRetry at soon ({llm_retry_count}/{MAX_RETRY})...")
            event_writer.send_event(
                event=AgentStreamEvent.RUNTIME_WARNING, 
                target=target,
                data={
                    "event_name": "bad_request_warning",
                    "content": {
                        "message": e.message,
                        "retry": llm_retry_count
                    }
                }
            )
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
            event_writer.send_event(
                event=AgentStreamEvent.RUNTIME_WARNING, 
                target=target,
                data={
                    "event_name": "rate_limit_warning",
                    "content": {
                        "message": e.message,
                        "retry": llm_retry_count
                    }
                }
            )
            if llm_retry_count < MAX_RETRY and  LlmNodeAdapter.guess_exception_type(str(e)) == 'rate_limit':
                return Command(
                    update={
                        "llm_retry_count": llm_retry_count,
                        "error": "rate_limit"
                    },
                )
            else:
                raise e

        logger.info(f"[llm_call] Generate chunks num: {chunk_num}")

        # End streaming
        event_writer.send_event(
            event=AgentStreamEvent.LLM_STREAM_END, 
            target=target,
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
                "llm_retry_count": 0,
                "context_compress_level": 0 if state.get("context_compress_level", 0) <= 2 else 3,
                "error": "",
                "error_detail": "",
                "loaded_skills_cache": new_skills_cache,
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
        target = state.get("target")
        history_id = state.get("history_id")
        timestamp = state.get("timestamp")

        config = state.get("config")
        model_name = config.get("model_name")
        model_provider = config.get("models_provider")

        event_writer = AgentStreamWriter(generation_id)

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
                client_id, history_id, client_message, state.get("parent_node_id")
            )
            
            event_writer.send_event(
                event=AgentStreamEvent.LLM_STREAM_END, 
                target=target,
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

            dedup_map = {}
            for msg in tool_msg_list:
                # Always overwrite to keep the latest message for same id
                dedup_map[msg.tool_call_id] = msg

            deduped_tool_msgs = list(dedup_map.values())

            # Persist all tool messages in batch
            for msg in deduped_tool_msgs:
                tool_message = ai_context_manager.create_dict_message(
                    generation_id,
                    msg,
                    timestamp,
                    fallback_model_name=model_name,
                    fallback_model_provider=model_provider,
                    fallback_timestamp=timestamp
                )
                await ai_context_manager.append_to_messages(
                    client_id, history_id, tool_message, state.get("parent_node_id")
                )
            
            event_writer.send_event(
                event=AgentStreamEvent.LLM_STREAM_END, 
                target=target,
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
                client_id, history_id, client_message, state.get("parent_node_id")
            )
            
            event_writer.send_event(
                event=AgentStreamEvent.LLM_STREAM_END, 
                target=target,
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
