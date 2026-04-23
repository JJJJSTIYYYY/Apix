import json
from typing import Dict, Literal, Tuple
import time
import asyncio
from dataclasses import asdict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from apix_agent.apix_agent_core.agent_factory.prompt import *
from apix_agent.apix_agent_core.LLM.llm_adapter import LlmNodeAdapter
from apix_agent.apix_agent_core.agent_factory.agent_node import *
from apix_agent.apix_agent_core.tools.registry import get_available_tools
from apix_agent.global_config import BASE_DIR, OUTPUT_GRAPH_PNG, GRAPH_CACHE_TTL, GRAPH_CACHE_CLEAN_INTERVAL
from apix_agent.commons.type_def import MainAgentState, SubAgentState, AgentConfigSchema
from apix_agent.commons.logger import logger


class AgentCreator:

    def __init__(self):
        # key   -> hash_key
        # value -> (CompiledStateGraph, expire_timestamp)
        self.graph_cache: Dict[str, Tuple[CompiledStateGraph, float]] = {}

        # Lock is still needed because graph_cache is accessed
        # from async context + sync code paths
        self._graph_cache_lock = asyncio.Lock()

        # Async background task (not started here)
        self._graph_cache_clean_task: asyncio.Task | None = None


    def _collect_permission(self, config: AgentConfigSchema, permission_level: Literal["main", "sub"]) -> list:
        pure_chat_on = config.get("pure_chat_on", False)
        enable_file_opration = bool(config.get("enable_file_opration", False))
        enable_web_search = bool(config.get("enable_web_search", False))
        enable_knowledge_retrieval = bool(config.get("enable_knowledge_retrieval", False))
        enable_command_opration = bool(config.get("enable_command_opration", False))
        enable_skill_load = bool(config.get("enable_skill_load", False))
        enable_task_flow = bool(config.get("enable_task_flow", False))
        enable_agent_assign = bool(config.get("enable_agent_assign", False))
        enable_agent_swarm = bool(config.get("enable_agent_swarm", False))

    
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
        if enable_task_flow:
            agent_permission.append("task_flow")
        if (enable_agent_assign or enable_agent_swarm) and permission_level == 'main':
            agent_permission.append("sab_agent_assign")


        if "forbidden" in agent_permission:
            agent_permission = ["forbidden"]

        return agent_permission


    #--------------------------------------------------
    # Internal unified builder
    #--------------------------------------------------

    async def _create_agent_core(
        self,
        agent_name: str,
        agent_role: str,
        config: AgentConfigSchema,
        *,
        permission_level: Literal["main", "sub"],
        cache_prefix: str = "",
        enable_graph_png: bool = False,
        log_prefix: str = "[create_agent]",
    ):
        """
        Unified agent builder (for both main and sub agents).
        """

        logger.trace(f'[agent.py] [AI_Agent] {log_prefix} Enter')

        # Ensure config is JSON serializable
        config_dict = config if isinstance(config, dict) else asdict(config)

        hash_key = hash(
            cache_prefix + agent_name + json.dumps(config_dict, sort_keys=True, separators=(",", ":"))
        )

        now = time.time()

        # Cache lookup
        async with self._graph_cache_lock:
            cached = self.graph_cache.get(hash_key)
            if cached:
                agent_graph, expire_at = cached
                if expire_at > now:
                    # Refresh TTL on hit
                    self.graph_cache[hash_key] = (
                        agent_graph,
                        now + GRAPH_CACHE_TTL,
                    )
                    logger.success(f"{log_prefix} Get Agent From Cache (TTL refreshed).")
                    return agent_graph

        # Config extraction
        try:
            provider = config.get("models_provider")
            model = config.get("model_name")
            api_key = config.get("api_key", "")

            pure_chat_on = config.get("pure_chat_on", False)
            agent_permission = self._collect_permission(
                config=config,
                permission_level=permission_level
            )

        except Exception as e:
            return f"{e}"

        # LLM creation
        try:
            llm = LlmNodeAdapter.get_atapted_llm_node(
                provider=provider,
                model=model,
                api_key=api_key,
                config=config,
            )
            logger.success(f"{log_prefix} Get {model} from {provider}.")
        except Exception as e:
            return f"{e}"

        # Tools
        tools = get_available_tools(agent_permission)
        tool_set = [tool.name for tool in tools]

        if not pure_chat_on:
            if hasattr(llm, "bind_tools"):
                try:
                    llm = llm.bind_tools(tools)
                except NotImplementedError:
                    logger.warning(
                        f"{log_prefix} Binding tools to {model} from {provider} is not supported."
                    )

        # Graph build
        if permission_level == 'main':
            agent_node = MainAgentNode(llm=llm, tool_set=tool_set)
            graph = StateGraph(MainAgentState)
        elif permission_level == 'sub':
            agent_node = SubAgentNode(llm=llm, tool_set=tool_set)
            graph = StateGraph(SubAgentState)
        else:
            raise ValueError(f"Unknown permission_level: {permission_level}")

        graph.add_node("context_prepare", agent_node.context_prepare)
        graph.add_edge(START, "context_prepare")

        graph.add_node("context_summary", agent_node.context_summary)
        graph.add_edge("context_prepare", "context_summary")

        graph.add_node("llm_call", agent_node.llm_call)
        graph.add_edge("context_summary", "llm_call")

        graph.add_node("messages_persist", agent_node.messages_persist)
        graph.add_conditional_edges(
            "llm_call",
            agent_node.route_after_llm,
            {
                "retry": "llm_call",
                "summary": "context_summary",
                "ok": "messages_persist",
            },
        )

        if not pure_chat_on:
            graph.add_node("tools", ToolNode(tools))
            graph.add_conditional_edges(
                "messages_persist",
                agent_node.should_continue,
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

        # Optional graph visualization
        if enable_graph_png and OUTPUT_GRAPH_PNG:
            graph_png_path = "graph_with_tools.png" if not pure_chat_on else "graph_without_tools.png"
            img_bytes = agent_graph.get_graph(xray=True).draw_mermaid_png()
            with open(BASE_DIR + graph_png_path, "wb") as f:
                f.write(img_bytes)

        # Cache store
        async with self._graph_cache_lock:
            self.graph_cache[hash_key] = (
                agent_graph,
                time.time() + GRAPH_CACHE_TTL,
            )

        logger.success(f"{log_prefix} Compile Agent Finish.")
        return agent_graph


    #--------------------------------------------------
    # Public builders
    #--------------------------------------------------

    async def create_agent(self, agent_name: str, agent_role: str, config: AgentConfigSchema):
        """
        Create main agent.
        """
        return await self._create_agent_core(
            agent_name,
            agent_role,
            config,
            permission_level="main",
            cache_prefix="",
            enable_graph_png=True,
            log_prefix="[create_agent]",
        )


    async def create_sub_agent(self, agent_name: str, agent_role: str, config: AgentConfigSchema):
        """
        Create sub agent.
        """
        return await self._create_agent_core(
            agent_name,
            agent_role,
            config,
            permission_level="sub",
            cache_prefix="sub_",
            enable_graph_png=False,
            log_prefix="[create_sub_agent]",
        )
    
    
    #----------------------------------------------------------
    # Lifespan
    #----------------------------------------------------------

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


    async def _graph_cache_clean_loop(self):
        """
        Async background loop to periodically clean expired graph cache.
        This task is expected to be cancelled during shutdown.
        """
        try:
            while True:
                await asyncio.sleep(GRAPH_CACHE_CLEAN_INTERVAL)
                await self._clean_expired_graph_cache()
        except asyncio.CancelledError:
            # Task is being cancelled during shutdown
            logger.debug("[graph_cache] Cleaner task cancelled.")
            raise


    async def _clean_expired_graph_cache(self):
        now = time.time()
        removed = 0

        async with self._graph_cache_lock:
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
        
        

agent_creator = AgentCreator()
