import asyncio
import json
from typing import Annotated, Literal, Optional, TypedDict

from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.apix_agent_core.tools.prompt import REQUEST_USER_INPUT_PROMPT


class Question(TypedDict):
    question: str
    options: list[str]
    multiselection: Optional[bool]


@tool(description=REQUEST_USER_INPUT_PROMPT)
async def request_user_input(
    questions: list[Question],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    result = await event_writer.send_blocking_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "request_user_input",
            "tool_call_id": tool_call_id,
            "content": questions,
            "chunk_position": "start",
            "status": "success",
        }
    )

    parsed_result = str(result)
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            pass
    
    if isinstance(result, list):
        parsed_result = []
        for r in result:
            line0 = 'QUESTION:  \n' + (r.get('question', 'The question text is missing.') or 'The question text is missing.') + '  \n'
            resp = r.get('response', '[User did not provide an answer]') or '[User did not provide an answer]'
            parsed_resp = resp
            if isinstance(resp, list):
                parsed_resp = ''
                for ur in resp:
                    parsed_resp = parsed_resp + '- ' + str(ur) + '  \n'
            line1 = 'RESPONSE:  \n' + parsed_resp
            parsed_result.append(line0+line1)
        parsed_result = '\n\n'.join(parsed_result)
    
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_END, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "request_user_input",
            "tool_call_id": tool_call_id,
            "content": f"",
            "chunk_position": "end",
            "status": "success",
        }
    )

    return Command(update={
        "messages": [
            ToolMessage(
                ("## Get response from user:\n\n" + parsed_result) if parsed_result else "The user is currently unavailable or refuses to answer.",
                tool_call_id=tool_call_id
            )
        ]
    })