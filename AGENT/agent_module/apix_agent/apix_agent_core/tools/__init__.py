# -------------------------
# Sandbox tools
# -------------------------
from apix_agent.apix_agent_core.tools.basic_tools.sandbox import (
    configure_sandbox
)

# -------------------------
# Skill tools
# -------------------------
from apix_agent.apix_agent_core.tools.basic_tools.skills import (
    load_skill
)

# -------------------------
# File download tools
# -------------------------
from apix_agent.apix_agent_core.tools.basic_tools.file_manager import (
    get_file_by_id,
)

# -------------------------
# File read tools
# -------------------------
from apix_agent.apix_agent_core.tools.basic_tools.file_manager import (
    read_workspace_file,
    list_workspace_files,
)
from apix_agent.apix_agent_core.tools.basic_tools.agent_ocr import (
    agent_ocr_analysis,
    send_images_to_user,
)

# -------------------------
# File write / archive tools
# -------------------------
from apix_agent.apix_agent_core.tools.basic_tools.file_manager import (
    write_workspace_file,
    move_workspace_file,
    delete_workspace_file,
)
# from apix_agent.apix_agent_core.tools.code_runner.code_patcher import (
#     # apply_workspace_patch,
#     # modify_workspace_file,
# )

# -------------------------
# Todo management tools
# -------------------------
from apix_agent.apix_agent_core.tools.basic_tools.todo_list import (
    write_todos,
    read_memorandum,
    write_memorandum,    
)

# -------------------------
# Web tools
# -------------------------
from apix_agent.apix_agent_core.tools.web_search.search_tool import (
    search_links_by_keywords,
    fetch_content_by_urls,
)

# -------------------------
# Retrieval tools
# -------------------------
from apix_agent.apix_agent_core.tools.vector_search.retrieval_tool import (
    knowledge_base_retrieval
)

# -------------------------
# Execution tools (high privilege)
# -------------------------
from apix_agent.apix_agent_core.tools.code_runner.python_code_runner import execute_python_code
from apix_agent.apix_agent_core.tools.basic_tools.cmd import run_workspace_command
from apix_agent.apix_agent_core.tools.basic_tools.server_check import check_server

# -------------------------
# Sub-Agent
# -------------------------
from apix_agent.apix_agent_core.tools.assistant.call_assistant import (
    assign_task,
    query_task_by_id,
    stop_task_by_id,
)

# -------------------------
# Dev / test tools
# -------------------------
from apix_agent.apix_agent_core.tools.basic_tools.test_tool import test_tool

# -------------------------
# Interface test task tools
# -------------------------
from apix_agent.apix_agent_core.tools.plugin.api_test import (
    write_test_log,
    update_test_task,
    get_test_task
)



__all__ = [
    # Sandbox configure
    "configure_sandbox",

    # Skill loader
    "load_skill",

    # File download
    "get_file_by_id",

    # File read
    "read_workspace_file",
    "list_workspace_files",
    "agent_ocr_analysis",
    "send_images_to_user",

    # File write
    # "apply_workspace_patch",
    "write_workspace_file",
    # "modify_workspace_file",
    "delete_workspace_file",
    "move_workspace_file",

    # Todos management
    "write_todos",
    "read_memorandum",
    "write_memorandum",

    # Web
    "search_links_by_keywords",
    "fetch_content_by_urls",

    # Knowledge Retrieval
    "knowledge_base_retrieval",

    # Execution (high privilege)
    "execute_python_code",
    "run_workspace_command",

    # Sub-agent
    "assign_task",
    "query_task_by_id",
    "stop_task_by_id",

    # Dev / test
    "test_tool",
    "check_server",

    # interface test
    "write_test_log",
    "update_test_task",
    "get_test_task"
]
