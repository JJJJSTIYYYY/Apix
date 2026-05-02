import time
from typing import Annotated

from langchain.messages import ToolMessage
from langchain.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from apix_agent.apix_event_pipe.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.apix_agent_core.agent_team_task.task_manager import task_manager
from apix_agent.commons.logger import logger
from apix_agent.commons.type_def import MainAgentState, SubAgentState


@tool
async def assign_sub_assistant(
    agent_identity: str,
    system_prompt: str,
    task_description: str,
    instruction: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Delegate a task to a sub-assistant.

    This tool creates a sub-agent with the same capabilities as you (include callable tools, available skills and so on).
    The sub-agent will autonomously work to complete the task.

    Once the task is assigned, this tool returns immediately.

    ## When to Use
    Use this tool when:
    - The task may take a long time to complete.
    - The user explicitly asks you to assign some work to another assistant.
    - You are continuing a previous conversation with the sub-assistant (Use the same `agent_identity` in this case).

    Typical scenarios:
    - Background processing
    - Delegating complex or time-consuming work

    ## When NOT to Use
    Do NOT use this tool when:
    - The task is simple and can be completed directly.
    - The user explicitly asks you to handle the task yourself.
    - The task depends heavily on your current reasoning context.

    ## How to Write the Task

    task_description:
        Provide a concise description of the task's final goal. This description is visible to you and the user, but not to the sub-agent.
        - After assigning the task → add this description to your TODO list and mark TODO as **in progress**.
        - When the task is compeleted → mark TODO as **completed**.

    instruction:
        The detailed instructions for the sub-agent.
        It should include:
        - A detailed task goal
        - task context
        - workspace directory (create one if directory is not exist on disk)
        - relevant information
        - constraints (list clearly)
        - expected output format (if any)
        
        The instruction must be self-contained because the sub-agent
        does not have access to your conversation history or reasoning content.
        Do not reference previous messages such as "above", "earlier", or "previous analysis".

    ## Args
        agent_identity (str): Sub-agent's name and role in format `name[role]`, e.g: `Alice[Coder]`
        system_prompt (str): System prompt that used to define Sub-agent's characteristics
        task_description (str): The final objective of the task.
        instruction (str): Detailed instructions for the sub-agent.

    ## Returns
        str: task id.
    """

    assistant_name = agent_identity
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "assign_sub_assistant",
            "tool_call_id": tool_call_id,
            "content": f"Assign task to {assistant_name}...",
            "chunk_position": "start",
            "status": "success",
        }
    )

    # -------------------------
    # Validate inputs
    # -------------------------

    if not assistant_name or not task_description or not instruction:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_call_id": tool_call_id,
                "tool_name": "assign_sub_assistant",
                "content": "Error: No props specified.",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Error: No assistant_name / task_description / instruction specified.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    # -------------------------
    # Start a sub-assistant
    # -------------------------

    try:
        parent_state: MainAgentState = state.copy()
        if parent_state.get("agent_role") == "main_agent":
            agent_role = "sub_agent"
        elif parent_state.get("agent_role") == "team_leader":
            agent_role = "team_worker"
        else:
            raise PermissionError("You don't have the permission to assign a task.")

        input = {
            "role": "human",
            "content": instruction
        }

        initial_config = parent_state.get("config")
        initial_config["role_prompt"] = {
            "name": agent_identity,
            "definition": system_prompt,
        }
        initial_config["higher_role_prompt_permission"] = True

        loaded_skills_cache = state.get("loaded_skills_cache", [])
        new_skills_cache = []
        for name, injected, guide in loaded_skills_cache:
            new_skills_cache.append((name, False, guide))

        initial_state: SubAgentState = {
            **parent_state,
            "agent_name": assistant_name,
            "agent_role": agent_role,
            "history_id": "sub_" + parent_state.get("history_id", ""),
            "input": input,
            "re_generate": False,
            "messages": [],
            "current_tool_calls": 0,
            "longterm_memory": "",
            "shortterm_memory": "",
            "rule_prompt": "",
            "runtime_prompt": "",
            "llm_calls": 0,
            "sandbox": "",
            "todos": [],
            "memorandum": [],
            "skills": [],
            "loaded_skills_cache": new_skills_cache,
            "final_goal": task_description,
            "task_id": "",
            "start_timestamp": int(time.time()),
            "finish_timestamp": 0,
            "status": "pending",
            "errors": "",
            "outputs": "",
            "config": initial_config,
            "llm_retry_count": 0,
            "context_compress_level": 0,
            "context_fold_split_mark": [],
            "error": "",
        }
        config = state.get("config")

        task_id = await task_manager.submit_task(
            initial_state=initial_state,
            config=config,
            agent_name=assistant_name,
        )

        if not task_id:
            raise RuntimeError(f"Failed to assign task to {assistant_name}.")
        
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "assign_sub_assistant",
                "tool_call_id": tool_call_id,
                "content": f"{assistant_name}: {task_description}",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Assign task to {agent_identity} successfully.\nTask id: {task_id}\n",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except Exception as e:
        logger.exception(f'[assign_sub_assistant] Error occurred: {str(e)}')
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "assign_sub_assistant",
                "tool_call_id": tool_call_id,
                "content": f"Error: Failed to assign task",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error: Failed to assign task: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )


@tool
async def query_sub_assistant(
    task_ids: list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Query the status, result, and logs of a previously assigned task.

    This tool retrieves the current progress or final result of a task
    that was created using the task delegation tool `assign_sub_assistant`.
    The task may still be running, so the result may not be available yet.

    ## When to Use
    Use this tool when:
    - You want to check the progress of a previously assigned task.
    - You need to retrieve the result of a task that may have finished.
    - The user explicitly asks about the status of a delegated task.
    - You forgot a task ID and need to retrieve it again (Use empty task_ids in this case).

    ## When NOT to Use
    Do NOT use this tool when:
    - The task was not created by the delegation tool.
    - You already have the result of the task.
    - The task was just assigned.

    ## Args
        task_ids (list[str]): The identifier of those tasks you want to query. Query all if empty.

    ## Returns
        Task status information in the following dictionary format:
        {
            "task_id": str, # Unique identifier of the task
            "agent_identity": str, # sub-agent's name and role for this task
            "final_goal": str, # Original goal/objective of the task
            "current_todo_list": list, # Optional: Current to-do list maintained by the sub-agent
            "duration": int # Total task execution time in seconds
            "status": str # Task running state
            "outputs": str # The text content generated by the sub-agent
            "errors": str # The error message generated by the task-system
        }
        
    ## Important Guidelines
    If you notice that all todos in current_todo_list are completed, but the task status still shows as `in_progress`, 
    that means the sub-agent is generating the final response. Please continue waiting before completed.
    """

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "query_sub_assistant",
            "tool_call_id": tool_call_id,
            "content": "Querying task...",
            "chunk_position": "start",
            "status": "success",
        }
    )
    
    if isinstance(task_ids, str):
        task_ids = [task_ids]

    # -------------------------
    # Start a sub-assistant
    # -------------------------

    try:
        results = await task_manager.query_tasks(
            history_id="sub_" + state.get("history_id", ""),
            task_ids=task_ids
        )

        if not results:
            results = "No result or logs found."
        
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "query_sub_assistant",
                "tool_call_id": tool_call_id,
                "content": "Query success",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        str(results),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except Exception as e:
        logger.exception(f'[query_sub_assistant] Error occurred: {str(e)}')
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "query_sub_assistant",
                "tool_call_id": tool_call_id,
                "content": "Error: Failed to query task",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error: Failed to query task: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )


@tool
async def stop_sub_assistant(
    task_ids: list[str],
    reason: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Stop one or more previously assigned tasks.

    This tool requests the task system to terminate running tasks
    that were created using the task delegation tool `assign_sub_assistant`.

    If a task is currently pending or in_progress, it will be canceled as soon as possible.
    If the task has already completed or failed, the stop request will have no effect.

    ## When to Use
    Use this tool when:
    - The user explicitly asks you to cancel a delegated task.
    - The delegated task is no longer needed.
    - The task is running incorrectly or producing unwanted results.
    - A newer task has replaced the old one.

    Typical scenarios:
    - The new task already includes the content or objective of the previous task.
    - The task has been running for a long time without producing any output.
    - The user no longer needs the result of the task.

    ## When NOT to Use
    Do NOT use this tool when:
    - The task has already completed or failed.
    - You only want to check the progress of a task (use `query_task_by_id` instead).
    - The task status is `in_progress` and outputs or current_todo_list is generated.

    ## Args
        task_ids (list[str]): The identifier of those tasks you want to stop. 
        reason (str): Why you are trying to stop those task.

    ## Returns
        Task stop result information in the following dictionary format:
        {
            "task_id": str, # Unique identifier of the task
            "status": str, # Updated task state after the stop request
            "message": str # Additional information about the stop operation
        }

    ## Important Guidelines
    Stopping a task does not guarantee immediate termination.
    The task system will attempt to stop the task gracefully.
    """
    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "stop_sub_assistant",
            "tool_call_id": tool_call_id,
            "content": f"Stopping task...",
            "chunk_position": "start",
            "status": "success",
        }
    )

    # -------------------------
    # Validate inputs
    # -------------------------

    if not task_ids:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "stop_sub_assistant",
                "tool_call_id": tool_call_id,
                "content": "Error: No task_id specified.",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "Error: No task_id specified.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
    
    if isinstance(task_ids, str):
        task_ids = [task_ids]

    # -------------------------
    # Start a sub-assistant
    # -------------------------

    try:
        results = await task_manager.stop_tasks(
            history_id="sub_" + state.get("history_id"),
            task_ids=task_ids,
            reason=reason
        )
        
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "stop_sub_assistant",
                "tool_call_id": tool_call_id,
                "content": "Stop success",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        str(results),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except Exception as e:
        logger.exception(f'[stop_sub_assistant] Error occurred: {str(e)}')
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "stop_sub_assistant",
                "tool_call_id": tool_call_id,
                "content": "Error: Failed to stop task",
                "chunk_position": "end",
                "status": "fail",
            }
        )
        
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error: Failed to stop task: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )