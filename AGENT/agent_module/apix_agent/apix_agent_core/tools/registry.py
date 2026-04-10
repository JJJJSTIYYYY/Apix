from apix_agent.apix_agent_core.tools import *
from apix_agent.global_config import CHECK_SERVER_HEALTH

# def get_all_tools(mode: str | list[str] = "default"):
#     """
#     Return a list of LangChain Tool objects.
#     Must return @tool-decorated objects ONLY.
#     """
#     tools = []
#     if mode == "forbidden":
#         return []

#     if isinstance(mode, str):
#         if mode == "default":
#             tools = [
#                 get_file_by_id,
#                 read_workspace_file,
#                 list_workspace_files,
#                 write_workspace_file,
#                 run_workspace_command,
#                 read_memorandum,
#                 write_memorandum,
#                 execute_python_code,
#                 agent_ocr_analysis,
#             ]
#         elif mode == "search":
#             tools = [
#                 search_links_by_keywords,
#                 fetch_content_by_urls,
#             ]
#         elif mode == "todo":
#             tools = [
#                 write_todos
#             ]
#         elif mode == "skill":
#             tools = [
#                 load_skill
#             ]
#         elif mode == "call_sub_agent":
#             tools = [
#                 assign_task,
#                 query_task_by_id,
#                 stop_task_by_id
#             ]
#         elif mode == "forign":
#             tools = [

#             ]
#         else:
#             tools = []

#     elif isinstance(mode, list):
#         if "forbidden" in mode:
#             return []
#         for m in mode:
#             tools.extend(get_all_tools(m))

#     if CHECK_SERVER_HEALTH:
#         tools.append(check_server)

#     # Deduplicate tools by tool.name (LangChain resolves tools by name)
#     unique_tools = {}
#     for tool in tools:
#         unique_tools[tool.name] = tool

#     return list(unique_tools.values())


def get_available_tools(permission: str | list[str] = ""):
    """
    Return a list of LangChain Tool objects.
    Must return @tool-decorated objects ONLY.

    Avaliable permission: 
    {"file_opration", "web_search", "knowledge_retrieval", "command_opration", "skill_load", "sab_agent_assign", "forbidden"}
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
            get_file_by_id,
            read_workspace_file,
            list_workspace_files,
            write_workspace_file,
            move_workspace_file,
            delete_workspace_file,
        ],
        "web_search": [
            search_links_by_keywords,
            fetch_content_by_urls,
        ],
        "knowledge_retrieval": [
            knowledge_base_retrieval
        ],
        "command_opration": [
            run_workspace_command,
            execute_python_code,
        ],
        "skill_load": [
            load_skill
        ],
        "sab_agent_assign": [
            assign_task,
            query_task_by_id,
            stop_task_by_id
        ],
        "default": [
            write_todos, 
            read_memorandum, 
            write_memorandum,  
            agent_ocr_analysis, 
            send_images_to_user
        ],
        "interface_test_mode": [
            write_test_log,
            update_test_task,
            get_test_task,
            get_file_by_id,
            read_workspace_file,
            list_workspace_files,
            write_workspace_file,
            run_workspace_command,
            execute_python_code,
        ]
    }

    tools = []

    # Collect tools from all modes
    for m in modes:
        tools.extend(tool_registry.get(m, []))

    # Optional health check tools
    if CHECK_SERVER_HEALTH:
        tools.append(check_server)
        # tools.append(test_tool)

    # Deduplicate tools by tool.name (LangChain resolves tools by name)
    unique_tools = {}
    for tool in tools:
        unique_tools[tool.name] = tool

    return list(unique_tools.values())