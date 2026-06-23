from typing import Annotated, List

from langchain.messages import ToolMessage
from langchain.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from apix_agent.apix_event_pipe.stream_event.agent_stream_writer import AgentStreamWriter, AgentStreamEvent
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.tools.web_search.manager import manager
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager
from apix_agent.apix_agent_core.tools.prompt import SEARCH_WEB_BY_KEYWORDS_PROMPT, SEARCH_WEB_BY_URLS_PROMPT


@tool(description=SEARCH_WEB_BY_KEYWORDS_PROMPT)
async def search_web_by_keywords(
    key_word: str | list[str],
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
            "tool_name": "search_web_by_keywords",
            "tool_call_id": tool_call_id,
            "content": key_word,
            "chunk_position": "start",
            "status": "success",
        }
    )

    if isinstance(key_word, list):
        key_word = " ".join(key_word)

    try:
        config = state.get("config", {})

        provider, search_id = await manager.submit_link_search(
            keyword=key_word,
            config=config,
        )
        results, images = await manager.wait_result(search_id)

        await ai_context_manager.append_info_message(
            state.get("generation_id"),
            state.get("client_id"),
            state.get("history_id"),
            state.get("timestamp"),
            {
                "key_word": [key_word],
                "link_provider": provider,
            },
            state.get("parent_node_id")
        )

        if not results and not images:
            msg = "No urls and images found, please try other keywords."

            event_writer.send_event(
                event=AgentStreamEvent.TOOL_EXEC_END, 
                target=target,
                data={
                    "event_name": "tool_exec_chunk_rtn",
                    "tool_name": "search_web_by_keywords",
                    "tool_call_id": tool_call_id,
                    "content": "Read 0 results.",
                    "chunk_position": "end",
                    "status": "success",
                }
            )

            return Command(update={
                "messages": [
                    ToolMessage(msg, tool_call_id=tool_call_id)
                ]
            })

        text_lines = image_lines = []
        if results:
            text_lines: List[str] = [f"# Get {len(results)} Results:"]
            for idx, item in enumerate(results, start=1):
                text_lines.append(
                    f"{idx}. {item.title}\n"
                    f"    URL: {item.url}\n"
                    f"    Describe: {item.describe}"
                )

        if images:
            image_lines: List[str] = [f"# Get {len(images)} Images:"]
            for idx, item in enumerate(images, start=1):
                image_lines.append(
                    f"{idx}. {item.name}\n"
                    f"    URL: {item.url}\n"
                    f"    Source: {item.host_page_url}"
                )

        result_text = "\n\n".join(text_lines) + "\n---\n" + "\n\n".join(image_lines)

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_web_by_keywords",
                "tool_call_id": tool_call_id,
                "content": f"Read {len(results)} results.",
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
        logger.exception(f"Failed to search online: {str(e)}")

        error_msg = f"Failed to search web by keyword(s) with error(s): {str(e)}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_web_by_keywords",
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
    

@tool(description=SEARCH_WEB_BY_URLS_PROMPT)
async def search_web_by_urls(
    urls: str | list[str],
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
            "tool_name": "search_web_by_urls",
            "tool_call_id": tool_call_id,
            "content": urls,
            "chunk_position": "start",
            "status": "success",
        }
    )

    if isinstance(urls, str):
        urls = [urls]

    if not urls:
        msg = "Empty url is not accepted."

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_web_by_urls",
                "tool_call_id": tool_call_id,
                "content": "No url provided",
                "chunk_position": "end",
                "status": "fail",
            }
        )

        return Command(update={
            "messages": [
                ToolMessage(msg, tool_call_id=tool_call_id)
            ]
        })

    try:
        config = state.get("config", {})

        provider, search_id = await manager.submit_content_fetch(
            urls=urls,
            config=config,
        )

        results = await manager.wait_result(search_id)

        if not results:
            msg = "No content fetched from the provided URL(s)."

            event_writer.send_event(
                event=AgentStreamEvent.TOOL_EXEC_END, 
                target=target,
                data={
                    "event_name": "tool_exec_chunk_rtn",
                    "tool_name": "search_web_by_urls",
                    "tool_call_id": tool_call_id,
                    "content": "Read 0 results.",
                    "chunk_position": "end",
                    "status": "success",
                }
            )

            return Command(update={
                "messages": [
                    ToolMessage(msg, tool_call_id=tool_call_id)
                ]
            })

        blocks: List[str] = []
        for idx, item in enumerate(results, start=1):
            blocks.append(
                f"** [{idx}] {item.title or 'Untitled'} **\n\n"
                f"` URL: {item.url} `\n\n"
                f"{item.content}\n\n"
            )

        result_text = ("\n---\n\n").join(blocks)

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_web_by_urls",
                "tool_call_id": tool_call_id,
                "content": f"Read {len(results)} results.",
                "chunk_position": "end",
                "status": "success",
            }
        )

        await ai_context_manager.append_info_message(
            state.get("generation_id"),
            state.get("client_id"),
            state.get("history_id"),
            state.get("timestamp"),
            {
                "urls": urls,
                "content_provider": provider,
            },
            state.get("parent_node_id")
        )

        return Command(update={
            "messages": [
                ToolMessage(result_text, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        logger.exception(f"Failed to search online: {str(e)}")

        error_msg = f"Failed to search web by url(s) with error(s): {str(e)}"

        event_writer.send_event(
            event=AgentStreamEvent.TOOL_EXEC_END, 
            target=target,
            data={
                "event_name": "tool_exec_chunk_rtn",
                "tool_name": "search_web_by_urls",
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