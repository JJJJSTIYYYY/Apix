# import asyncio
# from typing import Annotated

# from langchain.tools import tool, InjectedToolCallId
# from langgraph.prebuilt import InjectedState
# from langgraph.types import Command
# from langchain_core.messages import ToolMessage

# from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
# from apix_agent.global_config import TOOLS_MAX_OUTPUT_LENGTH
# from apix_agent.apix_agent_core.tools.prompt import RUN_WORKSPACE_COMMAND_PROMPT


# @tool(description=RUN_WORKSPACE_COMMAND_PROMPT)
# async def run_workspace_command(
#     command: str,
#     state: Annotated[dict, InjectedState],
#     tool_call_id: Annotated[str, InjectedToolCallId],
# ) -> Command:

#     target = state.get("target")
#     generation_id = state.get("generation_id")

#     event_writer = AgentStreamWriter(generation_id)
#     event_writer.send_event(
#         event=AgentStreamEvent.TOOL_EXEC_START, 
#         target=target,
#         data={
#             "event_name": "tool_exec_chunk_rtn",
#             "tool_name": "run_workspace_command",
#             "tool_call_id": tool_call_id,
#             "content": command,
#             "chunk_position": "start",
#             "status": "success",
#         }
#     )

#     container_id = state.get("sandbox")

#     if not container_id:
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "run_workspace_command",
#                 "tool_call_id": tool_call_id,
#                 "content": "Error: Sandbox not configured.",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )
        
#         return Command(update={
#             "messages": [
#                 ToolMessage(
#                     "Error: Sandbox not configured. Please info the user to configure it.",
#                     tool_call_id=tool_call_id
#                 )
#             ]
#         })

#     if not command.strip():
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "run_workspace_command",
#                 "tool_call_id": tool_call_id,
#                 "content": "Error: command is empty.",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )

#         return Command(update={
#             "messages": [
#                 ToolMessage("Error: command cannot be empty.", tool_call_id=tool_call_id)
#             ]
#         })

#     try:
#         # Execute inside container
#         cmd = [
#             "docker", "exec",
#             container_id,
#             "bash", "-lc", command
#         ]

#         process = await asyncio.create_subprocess_exec(
#             *cmd,
#             stdout=asyncio.subprocess.PIPE,
#             stderr=asyncio.subprocess.PIPE,
#         )

#         stdout, stderr = await asyncio.wait_for(
#             process.communicate(), 
#             timeout=600.0
#         )

#         output = stdout.decode() + stderr.decode()

#         if len(output) > TOOLS_MAX_OUTPUT_LENGTH:
#             output = output[:TOOLS_MAX_OUTPUT_LENGTH//2] + "\n\n...[output truncated]...\n\n" + output[-TOOLS_MAX_OUTPUT_LENGTH//2:]

#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "run_workspace_command",
#                 "tool_call_id": tool_call_id,
#                 "content": f"{len(output.strip())} characters output." if output.strip() else "Command executed successfully (no output).",
#                 "chunk_position": "end",
#                 "status": "success",
#             }
#         )

#         return Command(update={
#             "messages": [
#                 ToolMessage(
#                     output.strip() or "Command executed successfully (no output).",
#                     tool_call_id=tool_call_id
#                 )
#             ]
#         })
    
#     except asyncio.TimeoutError:
#         process.kill()
#         await process.wait()

#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "run_workspace_command",
#                 "tool_call_id": tool_call_id,
#                 "content": "Error: Command execution timed out after 600 seconds.",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )
        
#         return Command(update={
#             "messages": [
#                 ToolMessage(
#                     "Error: Command execution timed out after 600 seconds.",
#                     tool_call_id=tool_call_id
#                 )
#             ]
#         })

#     except Exception as e:

#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "run_workspace_command",
#                 "tool_call_id": tool_call_id,
#                 "content": f"Error: {str(e)}",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )

#         return Command(update={
#             "messages": [
#                 ToolMessage(
#                     f"Error: {str(e)}",
#                     tool_call_id=tool_call_id
#                 )
#             ]
#         })
    