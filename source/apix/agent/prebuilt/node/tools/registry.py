from langchain_core.tools.base import BaseTool

from apix_agent.apix_agent_core.tools import *


async def get_available_tools(
        permission: str | list[str] = "", 
        agent_role: str = "", 
        filter_by_name: list[str] = [], 
        workspace_configured: bool = False, 
        user_uid: str = ""
    ) -> list[BaseTool]:
    """
    Return a list of LangChain Tool objects.
    Must return @tool-decorated objects ONLY.

    Avaliable permission: 
    {"file_operation", "web_search", "knowledge_retrieval", "command_operation", "skill_load", "task_flow", "sub_agent_assign", "forbidden"}
    """
    if isinstance(permission, str):
        modes = [permission]
    else:
        modes = permission

    if "forbidden" in modes:
        return []

    # Tool registry mapping
    tool_registry = {
        "file_operation": [
            fetch_files,
            read_workspace_file,
            list_workspace_files,
            write_workspace_file,
            move_workspace_file,
            delete_workspace_file,
        ],
        "web_search": [
            search_web_by_keywords,
            search_web_by_urls,
        ],
        "knowledge_retrieval": [
            search_knowledge_base
        ],
        "command_operation": [
            run_workspace_command,
            run_python_code,
        ],
        "skill_load": [
            load_skill
        ],
        "sub_agent_assign": [
            assign_sub_assistant,
            query_sub_assistant,
            stop_sub_assistant
        ],
        "default": [
            write_todos, 
            read_memory,
            write_memory,  
            ocr_analysis,
            send_images,
            request_user_input
        ],
        "task_flow": [
            update_test_task,
            get_test_task,
            fetch_files,
            read_workspace_file,
            list_workspace_files,
            write_workspace_file,
            run_workspace_command,
            run_python_code,
        ]
    }

    tools: list[BaseTool] = []

    # Collect tools from all modes
    for m in modes:
        tools.extend(tool_registry.get(m, []))

    if user_uid:
        mcp_tools = await mcp_mgr.load_all_mcp_tools(user_uid)
        tools.extend(mcp_tools)

    # Deduplicate tools by tool.name
    filter_tools = {}
    for tool in tools:
        if filter_by_name and tool.name not in filter_by_name:
            continue
        if agent_role in ['sub_agent', 'team_worker']:
            if tool.name in forbiden_for_sub_agent:
                continue
        if tool.name in need_workspace_config_tools and not workspace_configured:
            continue
        filter_tools[tool.name] = tool

    return list(filter_tools.values())

# Tools in this set are not allowed to be called simultaneously in one tool_calls
conflict_tool_set = {"write_todos", "write_memory", "load_skill"}
forbiden_for_sub_agent = {"request_user_input", "send_images", "assign_sub_assistant", "query_sub_assistant", "stop_sub_assistant"}
need_workspace_config_tools = {
    "fetch_files", "read_workspace_file", "list_workspace_files", "write_workspace_file",
    "move_workspace_file", "delete_workspace_file", 
    "run_workspace_command", "run_python_code", "load_skill",
    "ocr_analysis", "send_images",
}