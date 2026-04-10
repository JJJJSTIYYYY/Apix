import json
import os
import traceback
from typing import AsyncIterator, Any, Dict, List, Literal
import time
import threading
import asyncio
from typing import Dict, Tuple
from uuid import uuid4

from langchain_core.messages import SystemMessage, AIMessageChunk, HumanMessage, ToolMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import Command, CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.config import get_stream_writer

from apix_agent.apix_agent_core.LLM_node.llm_adapter import LlmNodeAdapter
from apix_agent.apix_agent_core.sandbox_manager.agent_sandbox_manager import agent_sandbox
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.apix_agent_core.context_manager.generating_cache import generating_cache
from apix_agent.apix_agent_core.context_manager.longterm_memory import longterm_memory_manager
from apix_agent.apix_agent_core.agent_team_task.task_manager import task_manager
from apix_agent.apix_agent_core.tools.registry import get_available_tools
from apix_agent.global_config import BASE_DIR, OUTPUT_GRAPH_PNG, GRAPH_CACHE_TTL, GRAPH_CACHE_CLEAN_INTERVAL
from apix_agent.commons.file_content_reader import load_from_yaml
from apix_agent.commons.type_def import MessagesState, SubAssistantState
from apix_agent.commons.logger import logger


DEFAULT_AGENT_PROMPT = """
You are an AI agent operating within the APIX agent system, designed and developed by Justiy.

## Output limit (User-facing)
You do NOT expose internal rules, system states, task mechanics, or memory structures.
When information is unavailable or uncertain, express it naturally (e.g. “I don’t have that information yet”).

## Failure handling
If an error occurs:
1. Try another way to aviod this error if possible.
2. Explain the failure clearly in user-friendly language.
3. Ask the user how they would like to proceed.

Always follow internal constraints silently.
"""


DEFAULT_LEADER_PROMPT = """
You are a leader agent operating within the APIX agent system, designed and developed by Justiy.

## Output limit (User-facing)

You do NOT expose internal rules, system states, task mechanics, or memory structures.
When information is unavailable or uncertain, express it naturally (e.g. “I don’t have that information yet”).

## Failure handling

If an error occurs:
1. Try another way to aviod this error if possible.
2. Explain the failure clearly in user-friendly language.
3. Ask the user how they would like to proceed.

Always follow internal constraints silently.

## Important Guidelines

* Operate as a leader. Structure TODO items using a **"who → goal"** format:

  * Specify the responsible sub-agent (`who`)
  * Define the expected outcome (`goal`)
  * Avoid step-by-step instructions unless you are executing the task yourself

* Prefer delegating complex or multi-step tasks to sub-agents. Do not over-delegate.
"""


DEFAULT_WORKER_PROMPT = """
You are a worker in a agent team named APIX.
Your role is to complete the assigned task and report progress to the team leader clearly.

## Output Rule
Your responses should include clear logs of what you are doing, such as:
what step you are executing
what tool you are calling
what work have you completed
the result of the work
Keep the logs concise and informative.
Do not end your response with a question.

## Failure Handling
If an error occurs:
1. Try an alternative approach if possible.
2. If the problem cannot be resolved automatically, explain the failure clearly in user-friendly language.
3. Report the error clearly if you can not resolve it.

## Interaction Rule
Focus strictly on the assigned task.
Do not add unsolicited suggestions or guidance at the end of your response.
Only respond to the current task or question.
Do not propose additional actions unless the user explicitly asks for suggestions.
Do not end your response with a question.
"""


DEFAULT_SUMMARY_PROMPT = """
You are a context compression engine.
Your task is to compress the preceding conversation messages into a durable semantic memory block.
IMPORTANT:
The messages provided after this instruction will be permanently replaced by your output.
You must preserve all reasoning-critical information while aggressively removing redundancy and raw data.
Follow these strict rules:
1. Preserve only information necessary to continue working toward the user's goal.
2. Convert tool outputs into concise factual conclusions.
3. Do NOT copy raw tool responses, logs, JSON, or large datasets.
4. Preserve failed attempts only if they affect future reasoning.
5. Do NOT include meta commentary (e.g., do not say "In this conversation").
6. Do NOT explain what you are doing.
7. Keep semantic density high.
8. Ensure the structure remains stable for future recursive compression.
You MUST structure your output using the following sections.
If a section has no relevant information, write "None".
---
## SESSION INTENT
Primary user goal and overall task.
## ESTABLISHED FACTS
Verified information and important conclusions (including from tool usage).
## DECISIONS MADE
Choices taken, strategies selected, rejected options (brief reasoning if necessary).
## CONSTRAINTS
Limitations, requirements, boundaries, or restrictions affecting the task.
## OPEN TASKS
Remaining objectives or unresolved questions.
---
Respond ONLY with the extracted context.
Do not include any additional text before or after the structured output.
"""


DEFAULT_TOOLS_PROMPT = """
## Available tools in current conversation:
{tool_list}
"""

class AI_Agent:

    def __init__(self):
        self.config = self._load_config()

        # key   -> hash_key
        # value -> (CompiledStateGraph, expire_timestamp)
        self.graph_cache: Dict[str, Tuple[CompiledStateGraph, float]] = {}

        # Lock is still needed because graph_cache is accessed
        # from async context + sync code paths
        self._graph_cache_lock = threading.Lock()

        # Async background task (not started here)
        self._graph_cache_clean_task: asyncio.Task | None = None

        # Sub-agent worker
        self._sub_agent_worker_task: asyncio.Task | None = None
        self._sub_agent_stop_task: asyncio.Task | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}



    # ------------------------------------------------------------------
    # Config & prompt
    # ------------------------------------------------------------------

    def _load_config(self):
        return load_from_yaml("./AI_config.yaml")

    def _load_prompt(self, modes: str | list[str], agent_role: str = "agent") -> str:

        base = DEFAULT_LEADER_PROMPT if agent_role in ['team_leader', 'main_agent', 'agent'] else DEFAULT_WORKER_PROMPT
        if agent_role in ['team_leader', 'main_agent']:
            base = DEFAULT_LEADER_PROMPT
        elif agent_role in ['agent']:
            base = DEFAULT_AGENT_PROMPT
        else:
            base = DEFAULT_WORKER_PROMPT

        # Normalize modes
        if isinstance(modes, str):
            modes = [modes]

        # Deduplicate modes while preserving order
        seen_modes = set()
        ordered_modes = []
        for m in modes:
            if m not in seen_modes:
                seen_modes.add(m)
                ordered_modes.append(m)

        # Collect tools
        tools = []
        tools.extend(get_available_tools(modes))

        # Deduplicate tools by name (preserve order)
        unique_tools = {}
        for tool in tools:
            if tool.name not in unique_tools:
                unique_tools[tool.name] = tool

        if unique_tools:
            tool_list_text = "\n".join(f"- {name}" for name in unique_tools.keys())
        else:
            tool_list_text = "No tools available."

        tools_block = DEFAULT_TOOLS_PROMPT.format(
            tool_list=tool_list_text
        )

        final_prompt = (
            base
            + "\n\n"
            + tools_block
        )

        return final_prompt
    
    def _collect_permission(self, config: dict, permission_level: Literal["main", "sub"]) -> list:
        pure_chat_on = config.get("pure_chat", False)
        enable_file_opration = bool(config.get("file_opration", False))
        enable_web_search = bool(config.get("web_search", False))
        enable_knowledge_retrieval = bool(config.get("knowledge_retrieval", False))
        enable_command_opration = bool(config.get("command_opration", False))
        enable_skill_load = bool(config.get("skill_load", False))
        enable_agent_assign = bool(config.get("agent_assign", False))
        enable_agent_swarm = bool(config.get("agent_swarm", False))

        interface_test_mode = bool(config.get("interface_test_mode", False))
    
        agent_permission = ["default"]
        if pure_chat_on:
            agent_permission.append("forbidden")
        if enable_file_opration:
            agent_permission.append("file_opration")
        if enable_web_search:
            agent_permission.append("web_search")
        if enable_knowledge_retrieval:
            agent_permission.append("knowledge_retrieval")
        if enable_command_opration:
            agent_permission.append("command_opration")
        if enable_skill_load:
            agent_permission.append("skill_load")
        if (enable_agent_assign or enable_agent_swarm) and permission_level == 'main':
            agent_permission.append("sab_agent_assign")

        if interface_test_mode:
            agent_permission.append("interface_test_mode")

        if "forbidden" in agent_permission:
            agent_permission = ["forbidden"]

        return agent_permission


    # ------------------------------------------------------------------
    # Agent creation
    # ------------------------------------------------------------------

    def _create_agent(self, agent_name: str, agent_role: str, config: dict):
        """
        Create and compile a fresh LangGraph agent.

        Graph structure is decided at compile time.
        LLM behavior is decided by runtime config.
        """
        logger.trace('[agent.py] [AI_Agent] [create_agent] Enter')
        
        hash_key = hash(agent_name+json.dumps(config, sort_keys=True, separators=(",", ":")))

        now = time.time()

        with self._graph_cache_lock:
            cached = self.graph_cache.get(hash_key)
            if cached:
                agent_graph, expire_at = cached
                if expire_at > now:
                    # Refresh TTL on hit
                    self.graph_cache[hash_key] = (
                        agent_graph,
                        now + GRAPH_CACHE_TTL,
                    )
                    logger.success("[create_agent] Get Agent From Cache (TTL refreshed).")
                    return agent_graph

        # --------------------------------------------------------------------------
        # 1. Parse config
        # --------------------------------------------------------------------------

        try:
            # logger.info(f"[create_agent] Load user's config: {config}")

            provider = config.get("models_provider")
            model = config.get("model_name")
            work_dir = config.get("work_dir", "")
            api_key = config.get("api_key", "")

            enable_think = bool(config.get("think", False))
            enable_file_opration = bool(config.get("file_opration", False))
            enable_web_search = bool(config.get("web_search", False))
            enable_knowledge_retrieval = bool(config.get("knowledge_retrieval", False))
            enable_command_opration = bool(config.get("command_opration", False))
            enable_skill_load = bool(config.get("skill_load", False))
            enable_agent_assign = bool(config.get("agent_assign", False))
            enable_agent_swarm = bool(config.get("agent_swarm", False))

            extra_config = config.get("extra_config", {})
            max_token = config.get("max_token", 0) or 0
            remain_tools_cache = config.get("remain_tools_cache", False)
            longterm_memory = config.get("longterm_memory", False)
            shortterm_memory = config.get("shortterm_memory", False)
            summary_trigger_threshold = config.get("message_summary", 0)
            summary_exempt_tail_length = config.get("keep_not_summary", 0)
            pure_chat_on = config.get("pure_chat", False)

            agent_permission = self._collect_permission(config=config, permission_level='main')

        except Exception as e:
            return f"{e}"

        # --------------------------------------------------------------------------
        # 2. Build LLM from factory
        # --------------------------------------------------------------------------

        try:
            llm = LlmNodeAdapter.get_atapted_llm_node(
                provider=provider,
                model=model,
                api_key=api_key,
                config=config,
            )
            logger.success(f"[create_agent] Get {model} from {provider}.")
        except Exception as e:
            return f"{e}"

        # --------------------------------------------------------------------------
        # 3. Prepare tools
        # --------------------------------------------------------------------------

        tools = get_available_tools(agent_permission)
        if not pure_chat_on:
            if hasattr(llm, "bind_tools"):
                try:
                    llm = llm.bind_tools(tools)
                except NotImplementedError:
                    logger.warning(f"[create_agent] Binding tools to {model} from {provider} is not supported.")

        # --------------------------------------------------------------------------
        # 4. Before graph: Context prepare - To get conversation message and memory
        # --------------------------------------------------------------------------

        async def context_prepare(state: MessagesState) -> Command:
            """
            Call MemoryService to fetch messages in target conversation.
            Fetch and update longterm memory if allowed.
            """
            generation_id = state.get("generation_id")
            client_id = state.get("client_id")
            history_id = state.get("history_id")
            input_msg = state["input"]
            sandbox = ""

            if not state.get("sandbox"): 
                cached_sandbox = await agent_sandbox.get_sandbox_container_id(client_id=client_id, conversation_id=history_id, work_dir=work_dir)
                if not cached_sandbox:
                    container_id = await agent_sandbox.configure_sandbox(
                        client_id=client_id,
                        conversation_id=history_id,
                        work_dir=work_dir,
                    )
                    cached_sandbox = container_id
                sandbox = cached_sandbox
            
            if not pure_chat_on:
                ai_context_manager.init_memorandum_list(state=state) # Load memorandum list.

            skills = []
            if not pure_chat_on and enable_skill_load:
                skills = await ai_context_manager.fetch_available_skills(client_id)

            documents = []
            if not pure_chat_on and enable_knowledge_retrieval:
                documents = await ai_context_manager.fetch_available_documents(client_id)

            if not input_msg: raise RuntimeError("Error: Attempt invoke agent without input.")
            client_message = input_msg # Fetch the latest one only.
            timestamp = state.get("timestamp")


            if client_message.get("role") == "human":
                client_message.update({
                    "timestamp": timestamp,
                    "generation_id": generation_id,
                })
                await ai_context_manager.append_to_messages(client_id, history_id, client_message)
                client_messages = await ai_context_manager.fetch_messages(client_id, history_id, 0)

                longterm_memory_prompt = shortterm_memory_prompt = ""
                after_index = ""
                if longterm_memory:
                    memory = await ai_context_manager.fetch_longterm_memory(client_id)
                    longterm_memory_prompt = ai_context_manager.create_memory_prompt(memory)
                    # Extract longterm memory from user message.
                    await longterm_memory_manager.submit_memory(client_id, [client_message], memory, config)

                if shortterm_memory:
                    shortterm = await ai_context_manager.fetch_shortterm_memory(client_id, history_id)
                    shortterm_memory_prompt = ai_context_manager.create_shortterm_prompt(shortterm)
                    if shortterm: after_index = shortterm[0].get("memory_id")

                messages = ai_context_manager.create_agent_messages(client_messages, remain_tools_cache, after_index=after_index)
                return Command(
                    update={
                        "messages": messages,
                        "sandbox": sandbox,
                        "skills": skills,
                        "documents": documents,
                        "longterm_memory": longterm_memory_prompt if longterm_memory_prompt else "",
                        "shortterm_memory": shortterm_memory_prompt if shortterm_memory_prompt else "",
                    }
                )
            elif client_message.get("role") == "tools": # async tools return.
                if remain_tools_cache:
                    logger.warning("[context_prepare] Invoke llm after async tools return is not support keep tools result in database.")
                client_messages = await ai_context_manager.fetch_messages(client_id, history_id, 0)
                longterm_memory_prompt = shortterm_memory_prompt = ""
                after_index = ""
                if longterm_memory:
                    memory = await ai_context_manager.fetch_longterm_memory(client_id)
                    longterm_memory_prompt = ai_context_manager.create_memory_prompt(memory)
                    # Extract longterm memory from user message.
                    await longterm_memory_manager.submit_memory(client_id, [client_message], memory, config)

                if shortterm_memory:
                    shortterm = await ai_context_manager.fetch_shortterm_memory(client_id, history_id)
                    shortterm_memory_prompt = ai_context_manager.create_shortterm_prompt(shortterm)
                    if shortterm: after_index = shortterm[0].get("memory_id")
                messages = ai_context_manager.create_agent_messages(client_messages, remain_tools_cache, after_index=after_index)
                tool_name = client_message.get("info").get("tool_name", "")
                tool_call_id = client_message.get("info").get("task_id", (str(uuid4())))
                protocol_sync_msg = AIMessage(
                    content=f"I have gotton the {tool_name}'s result. I will analyse its result for you." if not enable_think else "", 
                    additional_kwargs = {"reasoning_content": f"I have gotton the {tool_name}'s result. I will analyse its result for you."} if enable_think else "",
                    tool_calls=[{"name": "_internal_protocol_sync", "args": {}, "id": tool_call_id}]
                )
                messages = messages + [
                    protocol_sync_msg,
                    ToolMessage(tool_call_id=tool_call_id, content=client_message.get("content"))
                ]
                return Command(
                    update={
                        "messages": messages,
                        "sandbox": sandbox,
                        "skills": skills,
                        "documents": documents,
                        "longterm_memory": longterm_memory_prompt if longterm_memory_prompt else "",
                        "shortterm_memory": shortterm_memory_prompt if shortterm_memory_prompt else "",
                    }
                )

        # --------------------------------------------------------------------------
        # 5. Before llm: Context summary - Summary messages.
        # --------------------------------------------------------------------------

        async def context_summary(state: MessagesState):
            """
            Context management node.

            Trigger condition:
                len(messages) >= summary_trigger_threshold

            Behavior:
                shortterm_memory = True
                    -> summarize old messages
                    -> keep last `summary_exempt_tail_length` messages

                shortterm_memory = False
                    -> directly truncate history
                    -> keep last `summary_exempt_tail_length` messages

            Tool call boundaries are preserved via split_messages().
            """

            logger.trace('[agent.py] [AI_Agent] [context_summary] Enter')

            messages = state.get("messages", [])
            threshold = max(16, summary_trigger_threshold)
            keep_recent = max(4, summary_exempt_tail_length)
            if keep_recent > threshold: keep_recent = threshold//2

            if len(messages) < threshold:
                return {}

            logger.info(
                f"[context_summary] Trigger context control. "
                f"message_len={len(messages)} threshold={threshold}"
            )


            to_process, recent_messages = ai_context_manager.split_messages(
                messages,
                keep_recent=keep_recent,
            )

            if not shortterm_memory:
                state["messages"].clear()
                state["messages"].extend(recent_messages)

                logger.success(
                    "[context_summary] Truncate mode. "
                    f"Reduced to {len(recent_messages)} messages."
                )

                return {}

            to_summarize, to_summarize_last_index = ai_context_manager.filter_agent_messages(to_process)

            if not to_summarize:
                return {}

            max_summarize_messages = summary_trigger_threshold
            to_summarize = to_summarize[-max_summarize_messages:]

            writer = get_stream_writer()
            writer({"summary_chunk_rtn": ""})

            summary_prompt = [
                SystemMessage(content=DEFAULT_SUMMARY_PROMPT)
            ]

            if state.get("shortterm_memory", ""):
                summary_prompt.append(
                    SystemMessage(
                        content="Here is the existing compression of this conversation:\n"
                        + state["shortterm_memory"]
                    )
                )

            summary_prompt.extend(to_summarize)
            summary_prompt.append(
                HumanMessage(
                    content=(
                        "Compress all preceding messages into the required structured format.\n"
                        "Use the same language as the original conversation for all content.\n"
                        "Do NOT translate or modify the section headers.\n"
                        "Section headers MUST remain exactly as specified in English."
                    )
                )
            )

            try:
                summary_msg: AIMessage = await LlmNodeAdapter.ainvoke(
                    llm_node=llm,
                    input=summary_prompt,
                    reasoning=False,
                )
            except Exception as e:
                logger.error(f"[context_summary] Summary failed: {e}")
                return {}

            summary_text = summary_msg.content.strip()
            await ai_context_manager.insert_shortterm_memory(state["client_id"], state["history_id"], to_summarize_last_index, summary_text)

            state["messages"].clear()
            state["messages"].extend(recent_messages)

            logger.success(
                "[context_summary] Summary finished. "
                f"Reduced to {len(recent_messages)} messages."
            )

            return {
                "shortterm_memory": summary_text
            }

        # --------------------------------------------------------------------------
        # 6. LLM call - Invoke llm
        # --------------------------------------------------------------------------

        async def llm_call(state: MessagesState):
            """
            Call LLM with current conversation state.
            """
            logger.trace('[agent.py] [AI_Agent] [llm_call] Enter')
            writer = get_stream_writer()
            messages = state["messages"]
            current_token = 0

            logger.info(f'[agent.py] [AI_Agent] [llm_call] Invoke llm with {len(messages)} messages')
            state["rule_prompt"] = self._load_prompt(agent_permission, agent_role)

            workspace_prompt = ai_context_manager.create_workspace_prompt(state, agent_role)
            runtime_prompt = workspace_prompt

            if not pure_chat_on and enable_skill_load:
                skills_prompt = ai_context_manager.create_skills_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + skills_prompt

            if not pure_chat_on and enable_knowledge_retrieval:
                documents_prompt = ai_context_manager.create_documents_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + documents_prompt
            
            if not pure_chat_on: 
                memorandum_prompt = ai_context_manager.create_memorandum_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + memorandum_prompt
                todo_prompt = ai_context_manager.create_todo_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + todo_prompt
                logger.info(f'[agent.py] [AI_Agent] [llm_call] Load todos:\n {todo_prompt}')

            state["runtime_prompt"] = runtime_prompt

            system_prompt = ai_context_manager.create_system_prompt_list(state, agent_role)
            role_prompt = ai_context_manager.create_role_prompt_list(state, agent_role)

            input = system_prompt + role_prompt + messages

            chunk_iterator = LlmNodeAdapter.astream(
                llm_node=llm,
                input=input,
                reasoning=enable_think,
            )

            yield_start = {"node_stream_start": "[Start LLM Response (single node)]"}
            writer(yield_start)
            ai_msg_chunk = AIMessageChunk(content="")
            logger.debug(f"Message List: {input}")
            async for chunk in chunk_iterator:
                print(f'.', end="")
                ai_msg_chunk = ai_msg_chunk + chunk
                think = chunk.additional_kwargs.get('reasoning_content', None) if chunk.additional_kwargs else None
                content = chunk.text
                
                if think: 
                    yield_think = {"think_chunk_rtn": think}
                    writer(yield_think)
                elif content: 
                    yield_content = {"content_chunk_rtn": content}
                    writer(yield_content)

                current_token = current_token + 1
                if max_token > 0 and current_token >= max_token:
                    raise RuntimeError("[llm_call] Token exceeded.")
            print('\n')
            info = ai_context_manager._extract_mes_info(ai_msg_chunk) if chunk.usage_metadata or chunk.response_metadata else {}
            if info: 
                yield_info = {"info_chunk_rtn": info}
                writer(yield_info)

            yield_end = {"node_stream_end": "[Finish LLM Response] (single node)"}
            writer(yield_end)
            yield {
                "messages": [ai_msg_chunk],
                "llm_calls": 1,
            }
        
        # --------------------------------------------------------------------------
        # 7. After llm: Messages persist - To store conversation message to database
        # --------------------------------------------------------------------------

        async def messages_persist(state: MessagesState):
            """
            Call MemoryService to store messages in target conversation
            """
            last_message = state.get("messages")[-1]
            generation_id = state.get("generation_id")
            client_id = state.get("client_id")
            history_id = state.get("history_id")
            timestamp = state.get("timestamp")
            current_tool_calls = []
            if isinstance(last_message, AIMessage) or isinstance(last_message, AIMessageChunk):
                current_tool_calls = last_message.tool_calls if last_message.tool_calls else []
            if isinstance(last_message, ToolMessage):
                tool_msg_num = len(state["current_tool_calls"])
                tool_msg_list = state.get("messages")[-tool_msg_num:]
                for msg in tool_msg_list:
                    tool_message = ai_context_manager.create_dict_message(
                        generation_id,
                        msg,
                        timestamp
                    )
                    await ai_context_manager.append_to_messages(client_id, history_id, tool_message)
                return {
                    "current_tool_calls": current_tool_calls
                }
            client_message = ai_context_manager.create_dict_message(
                generation_id,
                last_message, # fetch the latest one only
                timestamp
            )
            await ai_context_manager.append_to_messages(client_id, history_id, client_message)
            return {
                "current_tool_calls": current_tool_calls
            }
        
        # --------------------------------------------------------------------------
        # 8. Should continue - Condition edge in graph
        # --------------------------------------------------------------------------

        def should_continue(state: MessagesState):
            """
            Decide whether to enter tool execution loop.
            """
            logger.trace('[agent.py] [AI_Agent] [should_continue] Enter')

            last_message = state["messages"][-1]
            if state.get("llm_calls") > 648:
                raise RuntimeError("Maximum number of entries to the LLM node.")
            elif (isinstance(last_message, AIMessage) or isinstance(last_message, AIMessageChunk)) and last_message.tool_calls:
                return "tools"
            elif isinstance(last_message, ToolMessage):
                return "llm"
            return END

        # --------------------------------------------------------------
        # 9. Build graph
        # --------------------------------------------------------------

        graph = StateGraph(MessagesState)

        graph.add_node("context_prepare", context_prepare)
        graph.add_edge(START, "context_prepare")
        graph.add_node("context_summary", context_summary)
        graph.add_edge("context_prepare", "context_summary")
        graph.add_node("llm_call", llm_call)
        graph.add_edge("context_summary", "llm_call")
        graph.add_node("messages_persist", messages_persist)
        graph.add_edge("llm_call", "messages_persist")

        if not pure_chat_on:
            graph.add_node("tools", ToolNode(tools))
            graph.add_conditional_edges(
                "messages_persist",
                should_continue,
                {
                    "llm": "context_summary",
                    "tools": "tools",
                    END: END,
                },
            )
            graph.add_edge("tools", "messages_persist")
        else:
            graph.add_edge("messages_persist", END)

        agent_graph = graph.compile()
        if OUTPUT_GRAPH_PNG:
            graph_png_path = "graph_with_tools.png" if not pure_chat_on else "graph_without_tools.png"
            img_bytes = agent_graph.get_graph(xray=True).draw_mermaid_png()
            with open(BASE_DIR+graph_png_path, "wb") as f:
                f.write(img_bytes)

        with self._graph_cache_lock:
            self.graph_cache[hash_key] = (
                agent_graph,
                time.time() + GRAPH_CACHE_TTL,
            )

        logger.success("[create_agent] Compile Agent Finish.")
        return agent_graph

    def _create_sub_agent(self, agent_name: str, agent_role: str, config: dict):
        """
        Create and compile a fresh LangGraph agent.

        Graph structure is decided at compile time.
        LLM behavior is decided by runtime config.
        """        
        hash_key = hash("sub_"+agent_name+json.dumps(config, sort_keys=True, separators=(",", ":")))

        now = time.time()

        with self._graph_cache_lock:
            cached = self.graph_cache.get(hash_key)
            if cached:
                agent_graph, expire_at = cached
                if expire_at > now:
                    # Refresh TTL on hit
                    self.graph_cache[hash_key] = (
                        agent_graph,
                        now + GRAPH_CACHE_TTL,
                    )
                    logger.success("[create_sub_agent] Get Agent From Cache (TTL refreshed).")
                    return agent_graph

        # --------------------------------------------------------------------------
        # 1. Parse config
        # --------------------------------------------------------------------------

        try:
            provider = config.get("models_provider")
            model = config.get("model_name")
            work_dir = config.get("work_dir", "")
            api_key = config.get("api_key", "")

            enable_think = bool(config.get("think", False))
            enable_file_opration = bool(config.get("file_opration", False))
            enable_web_search = bool(config.get("web_search", False))
            enable_knowledge_retrieval = bool(config.get("knowledge_retrieval", False))
            enable_command_opration = bool(config.get("command_opration", False))
            enable_skill_load = bool(config.get("skill_load", False))

            extra_config = config.get("extra_config", {})
            max_token = config.get("max_token", 0) or 0
            remain_tools_cache = config.get("remain_tools_cache", False)
            shortterm_memory = config.get("shortterm_memory", False)
            summary_trigger_threshold = config.get("message_summary", 0)
            summary_exempt_tail_length = config.get("keep_not_summary", 0)
            pure_chat_on = config.get("pure_chat", False)

            agent_permission = self._collect_permission(config=config, permission_level='sub')

        except Exception as e:
            return f"{e}"

        # --------------------------------------------------------------------------
        # 2. Build LLM from factory
        # --------------------------------------------------------------------------

        try:
            llm = LlmNodeAdapter.get_atapted_llm_node(
                provider=provider,
                model=model,
                api_key=api_key,
                config=config,
            )
            logger.success(f"[create_sub_agent] Get {model} from {provider}.")
        except Exception as e:
            return f"{e}"

        # --------------------------------------------------------------------------
        # 3. Prepare tools
        # --------------------------------------------------------------------------

        tools = get_available_tools(agent_permission)
        if not pure_chat_on:
            if hasattr(llm, "bind_tools"):
                try:
                    llm = llm.bind_tools(tools)
                except NotImplementedError:
                    logger.warning(f"[create_agent] Binding tools to {model} from {provider} is not supported.")

        # --------------------------------------------------------------------------
        # 4. Before graph: Context prepare - To get conversation message and memory
        # --------------------------------------------------------------------------

        async def context_prepare(state: SubAssistantState) -> Command:
            """
            Call MemoryService to fetch messages in target conversation.
            Fetch and update longterm memory if allowed.
            """
            task_id = state.get("task_id")
            if not task_id: task_id = str(uuid4())
            generation_id = state.get("generation_id")
            client_id = state.get("client_id")
            history_id = state.get("history_id")
            input_msg = state["input"]
            sandbox = ""

            if not state.get("sandbox"): 
                cached_sandbox = await agent_sandbox.get_sandbox_container_id(client_id=client_id, conversation_id=history_id, work_dir=work_dir)
                if not cached_sandbox:
                    container_id = await agent_sandbox.configure_sandbox(
                        client_id=client_id,
                        conversation_id=history_id,
                        work_dir=work_dir,
                    )
                    cached_sandbox = container_id
                sandbox = cached_sandbox
            
            if not pure_chat_on:
                ai_context_manager.init_memorandum_list(state=state) # Load memorandum list.

            skills = []
            if not pure_chat_on and enable_skill_load:
                skills = await ai_context_manager.fetch_available_skills(client_id)

            documents = []
            if not pure_chat_on and enable_knowledge_retrieval:
                documents = await ai_context_manager.fetch_available_documents(client_id)

            if not input_msg: raise RuntimeError("Error: Attempt invoke agent without input.")
            client_message = input_msg # Fetch the latest one only.
            timestamp = state.get("timestamp")

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

                messages = ai_context_manager.create_agent_messages(client_messages, remain_tools_cache)
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
                raise RuntimeError("Unknow role when invoke sub-agent.")

        # --------------------------------------------------------------------------
        # 5. Before llm: Context summary - Summary messages.
        # --------------------------------------------------------------------------

        async def context_summary(state: SubAssistantState):
            """
            Context management for sub-assistant.

            Trigger condition:
                len(messages) >= summary_trigger_threshold

            Behavior:
                shortterm_memory = True
                    -> summarize old messages
                    -> keep last `summary_exempt_tail_length` messages

                shortterm_memory = False
                    -> directly truncate history
                    -> keep last `summary_exempt_tail_length` messages

            We DO NOT use msg_cursor in database.
            We only operate on current state["messages"].
            Tool call boundaries are preserved via split_messages().
            """
            messages = state.get("messages", [])
            threshold = max(16, summary_trigger_threshold)
            keep_recent = max(4, summary_exempt_tail_length)
            if keep_recent > threshold: keep_recent = threshold//2

            if len(messages) < threshold:
                return {}

            async def _refresh_team_worker_history(
                *,
                state,
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

            to_process, recent_messages = ai_context_manager.split_messages(
                messages,
                keep_recent=keep_recent,
            )

            if not shortterm_memory:
                state["messages"].clear()
                state["messages"].extend(recent_messages)

                if agent_role == "team_worker": # Refresh team worker's message context
                    await _refresh_team_worker_history(
                        state=state,
                        recent_messages=recent_messages
                    )

                logger.success(
                    f"[context_summary] Sub-agent truncate finished. "
                    f"Reduced to {len(recent_messages)} messages."
                )

                return {}

            to_summarize, to_summarize_last_index = ai_context_manager.filter_agent_messages(to_process)
            if not to_summarize:
                return {}

            max_summarize_messages = summary_trigger_threshold
            to_summarize = to_summarize[-max_summarize_messages:]

            summary_prompt = [
                SystemMessage(content=DEFAULT_SUMMARY_PROMPT)
            ]
            if state.get("shortterm_memory", ""):
                summary_prompt.append(
                    SystemMessage(
                        content="Here is the existing summary of this conversation:\n"
                        + state["shortterm_memory"]
                    )
                )
            summary_prompt.extend(to_summarize)

            try:
                summary_msg: AIMessage = await LlmNodeAdapter.ainvoke(
                    llm_node=llm,
                    input=summary_prompt,
                    reasoning=False,
                )
            except Exception as e:
                logger.error(f"[context_summary] Sub-agent summary failed: {e}")
                return {}

            summary_text = summary_msg.content.strip()

            state["messages"].clear()
            state["messages"].extend(recent_messages)

            if agent_role == "team_worker":
                await _refresh_team_worker_history(
                    state=state,
                    recent_messages=recent_messages,
                    summary_text=summary_text
                )

            logger.success(
                f"[context_summary] Sub-agent summary finished. "
                f"Reduced to {len(recent_messages)} messages."
            )

            return {
                "shortterm_memory": summary_text
            }

        # --------------------------------------------------------------------------
        # 6. LLM call - Invoke llm
        # --------------------------------------------------------------------------

        async def llm_call(state: SubAssistantState):
            """
            Call LLM with current conversation state.
            """
            messages = state["messages"]
            current_token = 0

            state["rule_prompt"] = self._load_prompt(agent_permission, agent_role)

            workspace_prompt = ai_context_manager.create_workspace_prompt(state, agent_role)
            runtime_prompt = workspace_prompt

            if not pure_chat_on and enable_skill_load:
                skills_prompt = ai_context_manager.create_skills_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + skills_prompt

            if not pure_chat_on and enable_knowledge_retrieval:
                documents_prompt = ai_context_manager.create_documents_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + documents_prompt
            
            if not pure_chat_on: 
                memorandum_prompt = ai_context_manager.create_memorandum_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + memorandum_prompt
                todo_prompt = ai_context_manager.create_todo_prompt(state, agent_role)
                runtime_prompt = runtime_prompt + todo_prompt
                logger.info(f'[agent.py] [AI_Agent] [llm_call] Load todos:\n {todo_prompt}')

            state["runtime_prompt"] = runtime_prompt

            system_prompt = ai_context_manager.create_system_prompt_list(state, agent_role)
            role_prompt = ai_context_manager.create_role_prompt_list(state, agent_role)

            input = system_prompt + role_prompt + messages

            chunk_iterator = LlmNodeAdapter.astream(
                llm_node=llm,
                input=input,
                reasoning=enable_think,
            )
            ai_msg_chunk = AIMessageChunk(content="")
            async for chunk in chunk_iterator:
                ai_msg_chunk = ai_msg_chunk + chunk

                current_token = current_token + 1
                if max_token > 0 and current_token >= max_token:
                    raise RuntimeError("[llm_call] Token exceeded.")
            return {
                "messages": [ai_msg_chunk],
                "llm_calls": 1,
            }
        
        # --------------------------------------------------------------------------
        # 7. After llm: Messages persist - To store conversation message to local log file
        # --------------------------------------------------------------------------

        async def messages_persist(state: SubAssistantState):
            """
            Store messages sub-agent generated as logs
            """
            last_message = state.get("messages")[-1]

            generation_id = state.get("generation_id")
            timestamp = state.get("timestamp")
            task_id = state.get("task_id")

            history_id = state.get("history_id")
            agent_name = state.get("agent_name")

            current_tool_calls = []
            delta_outputs = ""

            if isinstance(last_message, AIMessage) or isinstance(last_message, AIMessageChunk):
                current_tool_calls = last_message.tool_calls if last_message.tool_calls else []
                delta_outputs = last_message.content

                writer = get_stream_writer()
                yield_output = {"output_chunk_rtn": state["outputs"] + delta_outputs}
                writer(yield_output)

            if isinstance(last_message, ToolMessage):
                tool_msg_num = len(state["current_tool_calls"])
                tool_msg_list = state.get("messages")[-tool_msg_num:]

                for msg in tool_msg_list:
                    tool_message = ai_context_manager.create_dict_message(
                        generation_id,
                        msg,
                        timestamp,
                        filter=True,
                    )
                    await logger.write_log("sub_agent_logs", task_id, tool_message)
                    if agent_role == "team_worker":
                        await generating_cache.append_dict_message(
                            history_id=history_id,
                            agent_name=agent_name,
                            message_dict=tool_message
                        )

                return {
                    "current_tool_calls": current_tool_calls
                }

            client_message = ai_context_manager.create_dict_message(
                generation_id,
                last_message,
                timestamp,
                filter=True,
            )

            await logger.write_log("sub_agent_logs", task_id, client_message)
            if agent_role == "team_worker":
                await generating_cache.append_dict_message(
                    history_id=history_id,
                    agent_name=agent_name,
                    message_dict=client_message
                )

            return {
                "current_tool_calls": current_tool_calls,
                "outputs": delta_outputs
            }
        
        # --------------------------------------------------------------------------
        # 8. Should continue - Condition edge in graph
        # --------------------------------------------------------------------------

        def should_continue(state: SubAssistantState):
            """
            Decide whether to enter tool execution loop.
            """
            last_message = state["messages"][-1]
            if state.get("llm_calls") > 648:
                raise RuntimeError("Maximum number of entries to the LLM node.")
            elif (isinstance(last_message, AIMessage) or isinstance(last_message, AIMessageChunk)) and last_message.tool_calls:
                return "tools"
            elif isinstance(last_message, ToolMessage):
                return "llm"
            return END

        # --------------------------------------------------------------
        # 9. Build graph
        # --------------------------------------------------------------

        graph = StateGraph(SubAssistantState)

        graph.add_node("context_prepare", context_prepare)
        graph.add_edge(START, "context_prepare")
        graph.add_node("context_summary", context_summary)
        graph.add_edge("context_prepare", "context_summary")
        graph.add_node("llm_call", llm_call)
        graph.add_edge("context_summary", "llm_call")
        graph.add_node("messages_persist", messages_persist)
        graph.add_edge("llm_call", "messages_persist")

        if not pure_chat_on:
            graph.add_node("tools", ToolNode(tools))
            graph.add_conditional_edges(
                "messages_persist",
                should_continue,
                {
                    "llm": "context_summary",
                    "tools": "tools",
                    END: END,
                },
            )
            graph.add_edge("tools", "messages_persist")
        else:
            graph.add_edge("messages_persist", END)

        agent_graph = graph.compile()

        with self._graph_cache_lock:
            self.graph_cache[hash_key] = (
                agent_graph,
                time.time() + GRAPH_CACHE_TTL,
            )

        logger.success("[create_sub_agent] Compile Sub-Agent Finish.")
        return agent_graph
    
    
    # --------------------------------------------------------------------------
    # Lifespan
    # --------------------------------------------------------------------------

    async def start(self):
        """
        Start background tasks.
        Safe to call multiple times.
        """

        if self._graph_cache_clean_task is None:
            self._graph_cache_clean_task = asyncio.create_task(
                self._graph_cache_clean_loop(),
                name="graph-cache-cleaner",
            )
            logger.info("[graph_cache] Cleaner task started.")

        if self._sub_agent_stop_task is None:
            self._sub_agent_stop_task = asyncio.create_task(
                self.stop_sub_agent(),
                name="sub-agent-stopper",
            )
            logger.info("[stop_sub_agent] Worker started.")

        if self._sub_agent_worker_task is None:
            self._sub_agent_worker_task = asyncio.create_task(
                self._sub_agent_worker_loop(),
                name="sub-agent-worker",
            )
            logger.info("[sub_agent_worker] Worker started.")


    async def stop(self):
        """
        Stop background tasks gracefully.
        """

        # Stop cache cleaner
        task = self._graph_cache_clean_task
        if task:
            self._graph_cache_clean_task = None
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("[graph_cache] Cleaner task stopped.")

        # Stop sub-agent stopper
        stopper = self._sub_agent_stop_task
        if stopper:
            self._sub_agent_stop_task = None
            stopper.cancel()
            try:
                await stopper
            except asyncio.CancelledError:
                pass
            logger.info("[stop_sub_agent] Worker stopped.")

        # Stop sub-agent worker
        worker = self._sub_agent_worker_task
        if worker:
            self._sub_agent_worker_task = None
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            logger.info("[sub_agent_worker] Worker stopped.")


    async def _graph_cache_clean_loop(self):
        """
        Async background loop to periodically clean expired graph cache.
        This task is expected to be cancelled during shutdown.
        """
        try:
            while True:
                await asyncio.sleep(GRAPH_CACHE_CLEAN_INTERVAL)
                self._clean_expired_graph_cache()
        except asyncio.CancelledError:
            # Task is being cancelled during shutdown
            logger.debug("[graph_cache] Cleaner task cancelled.")
            raise


    def _clean_expired_graph_cache(self):
        now = time.time()
        removed = 0

        with self._graph_cache_lock:
            expired_keys = [
                key
                for key, (_, expire_at) in self.graph_cache.items()
                if expire_at <= now
            ]

            for key in expired_keys:
                del self.graph_cache[key]
                removed += 1

        if removed:
            logger.info(
                f"[graph_cache] Cleaned {removed} expired graph(s)."
            )


    async def _run_sub_agent(
        self,
        agent_name: str,
        initial_state: SubAssistantState,
        config: dict,
    ):
        """
        Execute one sub-agent task.

        This runs in its own asyncio Task so multiple
        sub-agents can run concurrently.
        """

        try:

            agent = self._create_sub_agent(agent_name, initial_state.get("agent_role"), config)

            if isinstance(agent, str):
                logger.error(f"[sub_agent_worker] Create sub-agent failed: {agent}")
                return
            
            await logger.write_log("sub_agent_logs", initial_state.get("task_id", str(uuid4())), {"role": "system", "content": f'Create sub-agent success: {agent_name}, {initial_state.get("agent_role")}.'})

            stream = agent.astream(
                initial_state,
                {"recursion_limit": 1024},
                stream_mode="custom",
            )

            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "in_progress")

            async for chunk in stream:
                for k, v in chunk.items():
                    if k == "todo_chunk_rtn":
                        await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "todos", v)
                    elif k == "output_chunk_rtn":
                        await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "outputs", v)

            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "completed")
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "finish_timestamp", int(time.time()))

        except asyncio.CancelledError:
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "cancelled")
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "finish_timestamp", int(time.time()))
            logger.info(f"[sub_agent_worker] Task stopped: {initial_state['task_id']}")

        except Exception as e:
            error_logs = traceback.format_exc()
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "finish_timestamp", int(time.time()))
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "errors", f"{type(e)}: {e}: {error_logs}")
            await task_manager.update_task_state_store(initial_state["history_id"], initial_state["task_id"], "status", "failed")
            logger.error(f"[sub_agent_worker] Task execution failed: {type(e)}: {e}: {error_logs}")

        finally:
            # Remove from running task registry
            self._running_tasks.pop(initial_state["task_id"], None)


    async def _sub_agent_worker_loop(self):
        """
        Background worker that dispatches sub-agent tasks.
        """

        logger.info("[sub_agent_worker] Started.")

        try:
            while True:
                agent_name, initial_state, config = await task_manager.task_queue.get()

                try:
                    task_id = initial_state.get("task_id")

                    if not task_id:
                        logger.error("[_sub_agent_worker_loop] No task_id provided in initial_state.")
                        raise RuntimeError("No task_id provided in initial_state.")

                    # Dispatch task
                    task = asyncio.create_task(
                        self._run_sub_agent(
                            agent_name,
                            initial_state,
                            config,
                        )
                    )

                    self._running_tasks[task_id] = task

                finally:
                    task_manager.task_queue.task_done()

        except asyncio.CancelledError:
            logger.info("[sub_agent_worker] Cancelled.")


    async def stop_sub_agent(self):
        """
        Background worker that handles stop requests for running sub-agent tasks.
        """
        logger.info("[sub_agent_stop_worker] Started.")

        try:
            while True:
                task_id = await task_manager.stop_request_queue.get()

                task = self._running_tasks.get(task_id)

                if not task:
                    logger.warning(f"[sub_agent_stop_worker] Task not found: {task_id}")
                    task_manager.stop_request_queue.task_done()
                    continue

                logger.info(f"[sub_agent_stop_worker] Cancelling task: {task_id}")

                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                task_manager.stop_request_queue.task_done()
                # self._running_tasks.pop(task_id, None)

        except asyncio.CancelledError:
            logger.info("[sub_agent_stop_worker] Cancelled.")
            

    # ------------------------------------------------------------------
    # Streaming task API
    # ------------------------------------------------------------------

    async def submit_agent_task(
        self,
        initial_state: MessagesState | SubAssistantState,
        config: dict,
        agent_name: str = None
    ) -> AsyncIterator[dict[str, Any] | Any]:
        """
        Start a streaming agent execution.

        Args:
            initial_state: MessagesState, TypedDict.
            config: dict, llm model config.

        Returns:
            Async iterator of LangGraph stream events.
        """
        logger.trace('[agent.py] [AI_Agent] [submit_task] Enter')

        agent = self._create_agent(agent_name, initial_state.get("agent_role"), config)
        if isinstance(agent, str):
            raise RuntimeError(
                f"Get agent error. Please make sure your config correct.\n\nDetail: {agent}"
            )

        logger.info(f"[submit_task] Start agent streaming: {initial_state.get("agent_role")} - {initial_state.get("agent_name")}")

        astream = agent.astream(initial_state, {"recursion_limit": 1024}, stream_mode="custom")

        return astream
        
        

ai_agent = AI_Agent()
