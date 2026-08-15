# import time
# from typing import Annotated

# from langchain.messages import ToolMessage
# from langchain.tools import tool, InjectedToolCallId
# from langgraph.prebuilt import InjectedState
# from langgraph.types import Command

# from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
# from apix_agent.apix_agent_core.agent_task.team_task_manager import team_task_manager
# from apix.common.utils.logger import logger
# from apix_agent.commons.type_def import AgentState, SubAgentState
# from apix_agent.apix_agent_core.tools.prompt import ASSIGN_SUB_ASSISTANT_PROMPT, QUERY_SUB_ASSISTANT_PROMPT, STOP_SUB_ASSISTANT_PROMPT


# @tool(description=ASSIGN_SUB_ASSISTANT_PROMPT)
# async def assign_sub_assistant(
#     agent_identity: str,
#     system_prompt: str,
#     task_description: str,
#     instruction: str,
#     state: Annotated[dict, InjectedState],
#     tool_call_id: Annotated[str, InjectedToolCallId]
# ) -> Command:

#     assistant_name = agent_identity
#     target = state.get("target")
#     generation_id = state.get("generation_id")

#     event_writer = AgentStreamWriter(generation_id)
#     event_writer.send_event(
#         event=AgentStreamEvent.TOOL_EXEC_START, 
#         target=target,
#         data={
#             "event_name": "tool_exec_chunk_rtn",
#             "tool_name": "assign_sub_assistant",
#             "tool_call_id": tool_call_id,
#             "content": f"Assign task to {assistant_name}...",
#             "chunk_position": "start",
#             "status": "success",
#         }
#     )

#     # -------------------------
#     # Validate inputs
#     # -------------------------

#     if not assistant_name or not task_description or not instruction:
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_call_id": tool_call_id,
#                 "tool_name": "assign_sub_assistant",
#                 "content": "Error: No props specified.",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )

#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         "Error: No assistant_name / task_description / instruction specified.",
#                         tool_call_id=tool_call_id,
#                     )
#                 ]
#             }
#         )

#     # -------------------------
#     # Start a sub-assistant
#     # -------------------------

#     try:
#         parent_state: AgentState = state.copy()
#         if parent_state.get("agent_role") == "main_agent":
#             agent_role = "sub_agent"
#         elif parent_state.get("agent_role") == "team_leader":
#             agent_role = "team_worker"
#         else:
#             raise PermissionError("You don't have the permission to assign a task.")

#         input = {
#             "role": "human",
#             "content": instruction
#         }

#         initial_config = parent_state.get("config")
#         initial_config["role_prompt"] = {
#             "name": agent_identity,
#             "definition": system_prompt,
#         }
#         initial_config["higher_role_prompt_permission"] = True

#         loaded_skills_cache = state.get("loaded_skills_cache", [])
#         new_skills_cache = []
#         for name, injected, guide in loaded_skills_cache:
#             new_skills_cache.append((name, False, guide))

#         initial_state: SubAgentState = {
#             **parent_state,
#             "agent_name": assistant_name,
#             "agent_role": agent_role,
#             "history_id": "sub_" + parent_state.get("history_id", ""),
#             "input": input,
#             "re_generate": False,
#             "messages": [],
#             "current_tool_calls": 0,
#             "longterm_memory": "",
#             "shortterm_memory": "",
#             "rule_prompt": "",
#             "runtime_prompt": "",
#             "llm_calls": 0,
#             "sandbox": "",
#             "todos": [],
#             "memorandum": [],
#             "skills": [],
#             "loaded_skills_cache": new_skills_cache,
#             "final_goal": task_description,
#             "task_id": "",
#             "start_timestamp": int(time.time()),
#             "finish_timestamp": 0,
#             "status": "pending",
#             "errors": "",
#             "outputs": "",
#             "config": initial_config,
#             "llm_retry_count": 0,
#             "context_compress_level": 0,
#             "context_fold_split_mark": [],
#             "error": "",
#         }
#         config = state.get("config")

#         task_id = await team_task_manager.submit_task(
#             initial_state=initial_state,
#             config=config,
#             agent_name=assistant_name,
#             generation_id=generation_id
#         )

#         if not task_id:
#             raise RuntimeError(f"Failed to assign task to {assistant_name}.")
        
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "assign_sub_assistant",
#                 "tool_call_id": tool_call_id,
#                 "content": f"{assistant_name}: {task_description}",
#                 "chunk_position": "end",
#                 "status": "success",
#             }
#         )

#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         f"Assign task to {agent_identity} successfully.\nTask id: {task_id}\n",
#                         tool_call_id=tool_call_id,
#                     )
#                 ],
#             }
#         )

#     except Exception as e:
#         logger.exception(f'Error occurred: {str(e)}')
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "assign_sub_assistant",
#                 "tool_call_id": tool_call_id,
#                 "content": f"Error: Failed to assign task",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )
        
#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         f"Error: Failed to assign task: {str(e)}",
#                         tool_call_id=tool_call_id,
#                     )
#                 ]
#             }
#         )


# @tool(description=QUERY_SUB_ASSISTANT_PROMPT)
# async def query_sub_assistant(
#     task_ids: list[str],
#     state: Annotated[dict, InjectedState],
#     tool_call_id: Annotated[str, InjectedToolCallId]
# ) -> Command:

#     target = state.get("target")
#     generation_id = state.get("generation_id")

#     event_writer = AgentStreamWriter(generation_id)
#     event_writer.send_event(
#         event=AgentStreamEvent.TOOL_EXEC_START, 
#         target=target,
#         data={
#             "event_name": "tool_exec_chunk_rtn",
#             "tool_name": "query_sub_assistant",
#             "tool_call_id": tool_call_id,
#             "content": "Querying task...",
#             "chunk_position": "start",
#             "status": "success",
#         }
#     )
    
#     if isinstance(task_ids, str):
#         task_ids = [task_ids]

#     # -------------------------
#     # Start a sub-assistant
#     # -------------------------

#     try:
#         results = await team_task_manager.query_tasks(
#             history_id="sub_" + state.get("history_id", ""),
#             task_ids=task_ids
#         )

#         if not results:
#             results = "No result or logs found."
        
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "query_sub_assistant",
#                 "tool_call_id": tool_call_id,
#                 "content": "Query success",
#                 "chunk_position": "end",
#                 "status": "success",
#             }
#         )

#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         str(results),
#                         tool_call_id=tool_call_id,
#                     )
#                 ],
#             }
#         )

#     except Exception as e:
#         logger.exception(f'Error occurred: {str(e)}')
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "query_sub_assistant",
#                 "tool_call_id": tool_call_id,
#                 "content": "Error: Failed to query task",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )
        
#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         f"Error: Failed to query task: {str(e)}",
#                         tool_call_id=tool_call_id,
#                     )
#                 ]
#             }
#         )


# @tool(description=STOP_SUB_ASSISTANT_PROMPT)
# async def stop_sub_assistant(
#     task_ids: list[str],
#     reason: str,
#     state: Annotated[dict, InjectedState],
#     tool_call_id: Annotated[str, InjectedToolCallId]
# ) -> Command:
    
#     target = state.get("target")
#     generation_id = state.get("generation_id")

#     event_writer = AgentStreamWriter(generation_id)
#     event_writer.send_event(
#         event=AgentStreamEvent.TOOL_EXEC_START, 
#         target=target,
#         data={
#             "event_name": "tool_exec_chunk_rtn",
#             "tool_name": "stop_sub_assistant",
#             "tool_call_id": tool_call_id,
#             "content": f"Stopping task...",
#             "chunk_position": "start",
#             "status": "success",
#         }
#     )

#     # -------------------------
#     # Validate inputs
#     # -------------------------

#     if not task_ids:
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "stop_sub_assistant",
#                 "tool_call_id": tool_call_id,
#                 "content": "Error: No task_id specified.",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )

#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         "Error: No task_id specified.",
#                         tool_call_id=tool_call_id,
#                     )
#                 ]
#             }
#         )
    
#     if isinstance(task_ids, str):
#         task_ids = [task_ids]

#     # -------------------------
#     # Start a sub-assistant
#     # -------------------------

#     try:
#         results = await team_task_manager.stop_tasks(
#             history_id="sub_" + state.get("history_id"),
#             task_ids=task_ids,
#             reason=reason
#         )
        
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "stop_sub_assistant",
#                 "tool_call_id": tool_call_id,
#                 "content": "Stop success",
#                 "chunk_position": "end",
#                 "status": "success",
#             }
#         )

#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         str(results),
#                         tool_call_id=tool_call_id,
#                     )
#                 ],
#             }
#         )

#     except Exception as e:
#         logger.exception(f'Error occurred: {str(e)}')
#         event_writer.send_event(
#             event=AgentStreamEvent.TOOL_EXEC_END, 
#             target=target,
#             data={
#                 "event_name": "tool_exec_chunk_rtn",
#                 "tool_name": "stop_sub_assistant",
#                 "tool_call_id": tool_call_id,
#                 "content": "Error: Failed to stop task",
#                 "chunk_position": "end",
#                 "status": "fail",
#             }
#         )
        
#         return Command(
#             update={
#                 "messages": [
#                     ToolMessage(
#                         f"Error: Failed to stop task: {str(e)}",
#                         tool_call_id=tool_call_id,
#                     )
#                 ]
#             }
#         )