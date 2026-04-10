import re
import time
import httpx
from typing import Any, Dict, List, Callable, Optional
from pydantic import BaseModel, Field, create_model
from langchain.tools import tool
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState

from apix_agent.commons.logger import logger
from apix_agent.global_config import TOOLS_SERVICE_URL


class ToolMaker:
    """
    ToolMaker dynamically builds LangChain tools which:
    - Submit async tool execution tasks to Tools service
    - Return submission result (task_id or semantic status)
    - Actual execution results are pushed asynchronously via Memory service

    ToolMaker entry: 
    build_tools() -> _fetch_tool_registry() -> _make_tool() -> _build_args_schema() + _make_submit_func() -> @tool wrapped callable
    build_tools() fetches tool registry, dynamically builds args_schema and submit wrapper, and returns LangChain @tool callables for agent initialization
    """

    SUPPORTED_REGISTRY_VERSION = "1.0"

    def __init__(self, tools_service_base_url: str):
        self._base_url = tools_service_base_url.rstrip("/")

    # ---------- public ----------

    async def build_tools(self) -> List[Callable]:
        """
        Build all tools registered in Tools service.
        Must be called before agent / graph initialization.
        """
        logger.info("[build_tools] Building forign tools for agent...")
        try:
            tools_meta = await self._fetch_tool_registry()

            seen = set()
            tools = []

            for meta in tools_meta:
                safe_name = self._sanitize_tool_name(meta["name"])
                if safe_name in seen:
                    raise ValueError(f"[build_tools] Duplicate tool name after sanitize: {safe_name}")
                seen.add(safe_name)

                tools.append(self._make_tool(meta))

            return tools
        except Exception as e:
            logger.error(f"[build_tools] Building forign tools error: {e}")
            return []

    # ---------- registry ----------

    async def _fetch_tool_registry(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self._base_url}/tools/registry")
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, dict):
            raise ValueError("[_fetch_tool_registry] Invalid registry format")

        if data.get("version") != self.SUPPORTED_REGISTRY_VERSION:
            raise RuntimeError(
                f"[_fetch_tool_registry] Unsupported registry version: {data.get('version')}"
            )

        tools = data.get("tools")
        if not isinstance(tools, list):
            raise ValueError("[_fetch_tool_registry] 'tools' must be a list")

        return tools

    # ---------- tool building ----------

    def _make_tool(self, meta: Dict[str, Any]) -> Callable:
        raw_name = meta["name"]
        safe_name = self._sanitize_tool_name(raw_name)
        description = meta.get("description", "")
        args_schema_meta = meta.get("args_schema", {})

        ArgsSchema = self._build_args_schema(
            tool_name=safe_name,
            params_schema=args_schema_meta,
        )

        tool_func = self._make_submit_func(
            tool_name=raw_name,
            tool_description=description,
        )

        return tool(
            safe_name,
            description=description,
            args_schema=ArgsSchema,
        )(tool_func)

    def _make_submit_func(self, tool_name: str, tool_description: str):
        """
        Create a tool submit function aligned with /execute/task API.
        """

        async def _tool_func(
            client_id: Annotated[str, InjectedState("client_id")],
            session_id: Annotated[str, InjectedState("session_id")],
            history_id: Annotated[str, InjectedState("history_id")],
            **kwargs,
        ) -> str:
            try:
                # Build payload aligned with tools service contract
                payload = {
                    "tool_name": tool_name,  # IMPORTANT: use raw tool name for task_hash
                    "client_id": client_id,
                    "history_id": history_id,
                    "payload": {
                        **kwargs,
                        # describe is optional but strongly recommended
                        "describe": kwargs.get("describe") or tool_description,
                        "timestamp": time.time(),
                    },
                }

                logger.info(f"[ToolSubmit] submit tool={tool_name}, payload={payload}")

                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{self._base_url}/execute/task",
                        json=payload,
                    )

                # ---- semantic response handling ----

                if resp.status_code >= 500:
                    logger.error(
                        f"[ToolSubmit] tools service error: {resp.status_code} {resp.text}"
                    )
                    return (
                        f"Tool '{tool_name}' failed due to internal service error. "
                        "Please try again later."
                    )

                if resp.status_code >= 400:
                    logger.warning(
                        f"[ToolSubmit] bad request: {resp.status_code} {resp.text}"
                    )
                    return (
                        f"Tool '{tool_name}' request was rejected. "
                        "Please check tool parameters."
                    )

                data = resp.json()
                task_id = data.get("task_id", "")
                message = data.get("message", "")

                if not task_id:
                    return (
                        f"Tool '{tool_name}' submission returned no task id. "
                        "Execution state is unknown."
                    )

                # Detect duplicate / already-running task
                if "already" in message.lower():
                    return (
                        f"Tool '{tool_name}' is already running. "
                        f"task_id={task_id}"
                    )

                return (
                    f"Tool '{tool_name}' submitted successfully. "
                    f"task_id={task_id}"
                )

            except httpx.TimeoutException:
                logger.exception(f"[ToolSubmit] timeout: {tool_name}")
                return (
                    f"Tool '{tool_name}' submission timed out. "
                    "The service may be unavailable."
                )

            except Exception as e:
                logger.exception(f"[ToolSubmit] unexpected error: {tool_name}")
                return (
                    f"Failed to submit tool '{tool_name}' due to unexpected error: {str(e)}"
                )

        return _tool_func

    # ---------- args_schema ----------

    def _build_args_schema(
        self,
        tool_name: str,
        params_schema: Dict[str, Dict[str, Any]],
    ) -> BaseModel:
        fields = {}

        for param_name, spec in params_schema.items():
            py_type = self._map_type(spec.get("type", "string"))
            description = spec.get("description", "")

            if spec.get("required", False):
                field_type = py_type
                default = ...
            elif "default" in spec:
                field_type = py_type
                default = spec["default"]
            else:
                field_type = Optional[py_type]
                default = None

            fields[param_name] = (
                field_type,
                Field(default=default, description=description),
            )

        return create_model(f"{tool_name.capitalize()}Args", **fields)

    # ---------- utils ----------

    @staticmethod
    def _sanitize_tool_name(name: str) -> str:
        """
        Ensure tool name is compatible with LangChain / OpenAI.
        """
        return re.sub(r"[^a-zA-Z0-9_]", "_", name)

    @staticmethod
    def _map_type(type_name: str):
        """
        Map registry schema types to Python types.
        """
        return {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }.get(type_name, str)



tool_maker = ToolMaker(TOOLS_SERVICE_URL)