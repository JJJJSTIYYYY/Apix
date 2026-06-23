from typing import Annotated, List

import httpx
from langchain.messages import ToolMessage
from langchain.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent import global_config
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.apix_agent_core.tools.prompt import SEARCH_KNOWLEDGE_BASE_PROMPT


@tool(description=SEARCH_KNOWLEDGE_BASE_PROMPT)
async def search_knowledge_base(
    query: str,
    document_ids: list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:

    logger.trace()

    target = state.get("target")
    generation_id = state.get("generation_id")

    event_writer = AgentStreamWriter(generation_id)
    event_writer.send_event(
        event=AgentStreamEvent.TOOL_EXEC_START, 
        target=target,
        data={
            "event_name": "tool_exec_chunk_rtn",
            "tool_name": "search_knowledge_base",
            "tool_call_id": tool_call_id,
            "content": query,
            "chunk_position": "start",
            "status": "success",
        }
    )

    # Normalize document_ids to list[str]
    if isinstance(document_ids, str):
        document_ids = [document_ids]

    if not document_ids:
        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_knowledge_base",
                "tool_call_id": tool_call_id,
                "content": "Empty query",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(
                    "[ERROR] document_ids can not be empty.\n\n"
                    "# Available Documents in Knewledge Base:\n\n"
                    "```json"
                    +str(state.get("documents"))
                    +"```", 
                    tool_call_id=tool_call_id
                )
            ]
        })

    try:
        config = state.get("config", {})
        base_url = global_config.FILE_SERVICE_URL.rstrip("/")
        endpoint = f"{base_url}/file/rag/fetch_document_chunks"

        payload = {
            "client_id": state.get("client_id"),
            "document_ids": document_ids,
            "model": config.get("embed_model"),
            "api_key": "",
            "query": query,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        messages = data.get("messages", []) if isinstance(data, dict) else []

        await ai_context_manager.append_info_message(
            state.get("generation_id"),
            state.get("client_id"),
            state.get("history_id"),
            state.get("timestamp"),
            {
                "key_word": query,
                "provider": "Milvus",
            },
            state.get("parent_node_id")
        )

        if not messages:
            msg = "No relevant knowledge base chunks found."

            event_writer.send_event(
                event=AgentStreamEvent.TOOL_EXEC_END, 
                target=target,
                data={
                    "event_name": "tool_exec_chunk_rtn",
                    "tool_name": "search_knowledge_base",
                    "tool_call_id": tool_call_id,
                    "content": "Read 0 chunks.",
                    "chunk_position": "end",
                    "status": "success",
                }
            )

            return Command(update={
                "messages": [
                    ToolMessage(msg, tool_call_id=tool_call_id)
                ]
            })

        text_lines: List[str] = [f"# Retrieved {len(messages)} Knowledge Base Chunks"]

        for idx, item in enumerate(messages, start=1):
            text = item.get("text", "") if isinstance(item, dict) else ""
            metadata = item.get("metadata", {}) if isinstance(item, dict) else {}

            source = metadata.get("source", "")
            document_id = metadata.get("document_id", "")
            file_name = metadata.get("file_name", "")

            text_lines.append(
                f"## Chunk {idx}\n"
                f"**Source**: {source}\n"
                f"**Document ID**: {document_id}\n"
                f"**File Name**: {file_name}\n\n"
                f"**Content**:\n{text}"
            )

        result_text = "\n\n---\n\n".join(text_lines)

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_knowledge_base",
                "tool_call_id": tool_call_id,
                "content": f"Read {len(messages)} chunks.",
                "chunk_position": "end",
                "status": "success",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(result_text, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        logger.exception(f"Failed search knowledge base: {str(e)}")

        error_msg = f"Failed to retrieve knowledge base chunks: {str(e)}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_knowledge_base",
                "tool_call_id": tool_call_id,
                "content": "Error: " + str(e),
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(error_msg, tool_call_id=tool_call_id)
            ]
        })