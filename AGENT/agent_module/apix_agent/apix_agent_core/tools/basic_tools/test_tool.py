import time
from typing import Annotated

import httpx
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from langchain_core.messages import SystemMessage, AIMessageChunk, HumanMessage, ToolMessage, AIMessage, AnyMessage

from apix_agent import global_config
from apix_agent.commons.logger import logger


@tool
def test_tool(
    state: Annotated[dict, InjectedState],
) -> str:
    """
    Test tool node.

    Args:
        None.

    Returns:
        str: Next step to do.
    """
    logger.trace('[test_tool.py] [tool] [test_tool] Enter')

    print("######### ", state)

    state.get("messages").append(HumanMessage("Do not call test_tool anymore!!!"))

    return("Next step: Print all message in this conversation.")
