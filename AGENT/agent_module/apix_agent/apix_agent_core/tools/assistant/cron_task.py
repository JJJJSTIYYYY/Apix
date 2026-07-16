from typing import Annotated

from langchain.messages import ToolMessage
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.apix_agent_core.agent_task.cron_task_manager import cron_task_manager
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.tools.prompt import SCHEDULE_CRON_TASK_PROMPT


@tool(description=SCHEDULE_CRON_TASK_PROMPT)
async def schedule_agent_task(
    cron_expression: str,
    prompt_to_invoke: str,
    execute_python: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    pass