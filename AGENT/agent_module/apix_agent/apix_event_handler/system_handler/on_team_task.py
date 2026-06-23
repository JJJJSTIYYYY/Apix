import asyncio
from typing import TypedDict

from apix_agent.commons.common_func import convert_generation_id_to_message_node_id
from apix_agent.apix_event_pipe.common_event.common_event_gateway import ApixEventItem, event_registry
from apix_agent.apix_event_pipe.stream_event.stream_event_gateway import action_handler
from apix_agent.apix_execution_context.agent_loop_context import AgentLoopContext
from apix_agent.commons.type_def import ApixIdentity
from apix_agent.commons.logger import logger


class TeamTaskCollection(TypedDict):
    target: ApixIdentity
    generation_ids: set[str]


# Collection: { history_id: TeamTaskCollection }
team_task_event_collection: dict[str, TeamTaskCollection] = {}
team_task_event_collection_lock = asyncio.Lock()


@event_registry.on_event("on_generation_team_task_completed", time_out=9999)
async def feedback_to_agent(event: ApixEventItem):
    """
    event data:
        event: "info",
        target: ApixIdentity,
        event_name: "on_generation_team_task_completed",
        content: {
            "generation_id": str,
            "history_id": str,
        }
        timestamp: float,
        generation_id: None

    event trigger when:
        All sub-agents assigned in one generation have finish their task.
    """

    target = event.target
    generation_id = event.content.get("generation_id")
    history_id = event.content.get("history_id")

    if not target:
        logger.warning("Unattached event received (target), skip handler.")
        return

    if not generation_id:
        logger.warning("Unattached event received (generation_id), skip handler.")
        return

    if not history_id:
        logger.warning("Unattached event received (history_id), skip handler.")
        return

    async with team_task_event_collection_lock:
        if history_id not in team_task_event_collection:
            team_task_event_collection[history_id] = {
                "target": target,
                "generation_ids": set(),
            }

        team_task_event_collection[history_id]["target"] = target
        team_task_event_collection[history_id]["generation_ids"].add(generation_id)

    # Wait for all active generations associated with the specified history.
    await action_handler.await_for_generation({
        "action": "await_for_generation",
        "data": {
            "client_id": target.get("id"),
            "history_id": history_id,
        }
    })

    # Only one concurrent handler can consume this history_id.
    async with team_task_event_collection_lock:
        item = team_task_event_collection.pop(history_id, None)

    # Already consumed by another handler.
    if item is None:
        event.accept()
        return

    target = item["target"]
    generation_id_set = item["generation_ids"]

    cached_chain = await AgentLoopContext.get_cached_message_chain(target)

    if not cached_chain:
        event.accept()
        return

    node_id_set = convert_generation_id_to_message_node_id(
        generation_id_set,
        "ai"
    )

    # All related nodes are no longer on the current branch.
    if node_id_set.isdisjoint(cached_chain):
        logger.info(
            "All related nodes are no longer on the current branch. "
            f"current branch: {cached_chain}; "
            f"collected task: {node_id_set};"
        )
        event.accept()
        return

    parent_id = cached_chain[-1]

    message_payload = {
        "role": "human",
        "content": "",
        "parent_id": parent_id,
        "extra": {
            "system_instruction": [(
                "/system-heartbeat: "
                "Sub-assistant task finish, use `query_sub_assistant` "
                "to view the detail."
            )]
        },
    }

    data = {
        "action": "chat_with_llm",
        "data": {
            "client_id": target.get("id"),
            "session_id": "",
            "history_id": history_id,
            "platform": target.get("platform", "default"),
            "messages": message_payload,
            "re_generate": False,
            "config": None,
        },
    }

    asyncio.create_task(
        action_handler.chat_with_llm(data)
    )

    event.accept()