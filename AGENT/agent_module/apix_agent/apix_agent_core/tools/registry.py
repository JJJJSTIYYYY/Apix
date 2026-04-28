from langchain_core.tools.base import BaseTool

from apix_agent.apix_agent_core.tools import *
from apix_agent.global_config import CHECK_SERVER_HEALTH


def get_available_tools(permission: str | list[str] = "", filter_by_name: list[str] = []) -> list[BaseTool]:
    """
    Return a list of LangChain Tool objects.
    Must return @tool-decorated objects ONLY.

    Avaliable permission: 
    {"file_opration", "web_search", "knowledge_retrieval", "command_opration", "skill_load", "task_flow", "sab_agent_assign", "forbidden"}
    """
    if isinstance(permission, str):
        modes = [permission]
    else:
        modes = permission

    if "forbidden" in modes:
        return []

    # Tool registry mapping
    tool_registry = {
        "file_opration": [
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
        "command_opration": [
            run_workspace_command,
            run_python_code,
        ],
        "skill_load": [
            load_skill
        ],
        "sab_agent_assign": [
            assign_sub_assistant,
            query_sub_assistant,
            stop_sub_assistant
        ],
        "default": [
            write_todos, 
            read_memorandum, 
            update_memorandum,  
            ocr_analysis, 
            send_images
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

    # Optional health check tools
    if CHECK_SERVER_HEALTH:
        tools.append(check_server)

    # Deduplicate tools by tool.name
    filter_tools = {}
    for tool in tools:
        if filter_by_name and tool.name not in filter_by_name:
            continue
        filter_tools[tool.name] = tool

    return list(filter_tools.values())


# Tools in this set are not allowed to be called simultaneously in one tool_calls
conflict_tool_set = {"write_todos", "update_memorandum", "load_skill"}