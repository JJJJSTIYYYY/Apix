import asyncio
from datetime import datetime
from typing import TypedDict

import httpx

from apix_agent.apix_agent_core.agent_task.cron_task_manager import cron_task_manager
from apix_agent.global_config import MEMORY_SERVICE_BASE_URL
from apix_agent.apix_execution_context.agent_loop_context import AgentLoopContext
from apix_agent.apix_event_pipe.stream_event.stream_event_gateway import action_handler
from apix_agent.commons.type_def import ApixIdentity
from apix_agent.apix_event_pipe.common_event.common_event_gateway import (
    ApixEventItem,
    event_registry
)
from apix_agent.apix_event_pipe.common_event.agent_event_writer import (
    AgentCommonEvent,
    event_pipe,
)
from apix_agent.commons.logger import logger


class CronTaskCollection(TypedDict):
    target: ApixIdentity
    event: ApixEventItem


# Queue: { history_id: asyncio.Queue }
cron_task_event_queue: dict[str, asyncio.Queue[CronTaskCollection]] = {}

# Worker: { history_id: asyncio.Task }
cron_task_loop_task: dict[str, asyncio.Task] = {}

cron_task_lock = asyncio.Lock()


@event_registry.on_event("on_cron_task_triggered", time_out=9999)
async def collect_triggered_cron_task(event: ApixEventItem):
    """
    event data:
        event: "info",
        target: ApixIdentity,
        event_name: "on_cron_task_triggered",
        content: {
            "task_id": str,
            "task_name": str,
            "repeat": Literal["once", "day", "week", "month", "year"],
            "scheduled_time": str, # ISO-8601
            "trigger_time": str, # ISO-8601
            "prompt": str,
            "execute_result": str,
            "execute_code_output": {
                "stdout": str,
                "stderr": str,
            },
            "extra_config": {
                "always_create_conversation": bool
            }
        }
        timestamp: float,
        generation_id: None

    event trigger when:
        A cron task is triggered.
    """
    target = event.target

    if not target:
        logger.warning("Unattached event received (target), skip handler.")
        return

    extra_config = event.content.get("extra_config", {})

    # Create a brand new conversation.
    if extra_config.get("always_create_conversation"):
        asyncio.create_task(
            execute_cron_task_new_conversation(
                target.copy(),
                event,
            )
        )

        event.accept()
        return

    # Use existing conversation.
    history_id = target.get("conversation_id")

    if not history_id:
        logger.warning("Unattached event received (history_id), skip handler.")
        return

    async with cron_task_lock:

        queue = cron_task_event_queue.setdefault(
            history_id,
            asyncio.Queue(),
        )

        await queue.put({
            "target": target,
            "event": event,
        })

        if (
            history_id not in cron_task_loop_task
            or cron_task_loop_task[history_id].done()
        ):
            cron_task_loop_task[history_id] = asyncio.create_task(
                cron_task_event_loop(history_id)
            )

    event.accept()


async def cron_task_event_loop(history_id: str):

    queue = cron_task_event_queue[history_id]

    while True:

        item = await queue.get()

        try:
            await execute_cron_task(
                target=item["target"],
                event=item["event"],
                await_idle=True,
            )

        except Exception:
            logger.exception("Failed to execute cron task.")

        finally:
            queue.task_done()

        if queue.empty():
            async with cron_task_lock:
                if queue.empty():
                    cron_task_event_queue.pop(history_id, None)
                    cron_task_loop_task.pop(history_id, None)
                    break


async def execute_cron_task_new_conversation(
    target: ApixIdentity,
    event: ApixEventItem,
):
    """
    Create a new conversation, then execute the cron task immediately.
    """

    workspace = target.get("conversation_id") or ""

    if workspace.startswith("dir://"):
        workspace = workspace.removeprefix("dir://")
    else:
        workspace = ""

    task_name = event.content.get("task_name", "New Conversation")

    try:

        async with httpx.AsyncClient() as client:

            response = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/conversation/create",
                json={
                    "client_id": target["id"],
                    "title": f"{task_name}",
                    "workspace": workspace,
                    "is_cron": True
                },
            )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            raise RuntimeError(
                data.get("messages") or
                "Failed to create conversation."
            )

        conversation_id = data["messages"]

        target["conversation_id"] = conversation_id
        
        await event_pipe.post_event(
            event=AgentCommonEvent.INFO,
            target=target,
            data={
                "event_name": "auto_create_conversation",
                "content": {
                    "conversation_meta": {
                        "conversation_uid": conversation_id,
                        "title": f"{task_name}",
                        "work_space": workspace,
                        "created_at": datetime.now().isoformat(),
                    }
                },
            },
        )

        await execute_cron_task(
            target=target,
            event=event,
            await_idle=False,
        )

    except Exception as e:
        logger.exception(
            f"Failed to create conversation for cron task '%s': {e}.",
            event.content.get("task_id"),
        )


async def execute_cron_task(
    target: ApixIdentity,
    event: ApixEventItem,
    await_idle: bool,
    workspace: str = ""
):
    """
    Execute one cron task by sending it to Agent.
    """

    history_id = target["conversation_id"]

    if await_idle:
        await action_handler.await_for_generation({
            "action": "await_for_generation",
            "data": {
                "client_id": target["id"],
                "history_id": history_id,
            },
        })

    cached_chain = await AgentLoopContext.get_cached_message_chain(target)

    parent_id = cached_chain[-1] if cached_chain else "-"

    task_name = event.content["task_name"]

    final_prompt = [(
        "/scheduled-heartbeat: "
        f"Cron task '{task_name}' triggered."
    )]
    execute_result = event.content.get("execute_result")
    user_comment = event.content.get("prompt")

    if not execute_result and not user_comment:
        return
    
    if execute_result:
        final_prompt.append((
            "## Context\n "
            f"```plain\n{execute_result}\n```"
        ))
    if user_comment:
        final_prompt.append((
            "## User Comments\n "
            f"```plain\n{user_comment}\n```"
        ))


    message_payload = {
        "role": "human",
        "content": "",
        "parent_id": parent_id,
        "extra": {
            "system_instruction": {
                "name": "cron_task",
                "task_name": task_name,
                "prompt": ["\n\n".join(final_prompt)],
            },
        },
    }

    data = {
        "action": "chat_with_llm",
        "data": {
            "client_id": target["id"],
            "session_id": "",
            "history_id": history_id,
            "platform": target.get("platform", "default"),
            "messages": message_payload,
            "re_generate": False,
            "config": None,
        },
    }

    await action_handler.chat_with_llm(data)