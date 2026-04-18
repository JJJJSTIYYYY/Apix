from typing import Annotated, List

from langchain.messages import ToolMessage
from langchain.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from apix_agent.apix_event_pipe.stream_writer import ApixStreamWriter, StreamEvent
from apix_agent.commons.logger import logger
from apix_agent.apix_agent_core.tools.web_search.manager import manager
from apix_agent.apix_agent_core.context_manager.context_process import ai_context_manager


@tool
async def search_web_by_keywords(
    key_word: str | list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Search the web for pages related to given keyword(s) and return a list of results
    containing the page title, URL, and a short description snippet.
    The search results may contain images.

    This tool only provides search results (metadata).
    It does NOT retrieve the full content of webpages.

    Args:
        key_word (str | list[str]): One or more search keywords.
            
    Returns:
        str: A tool message containing formatted webpage results and optional image results.

    ## When to Use This Tool
    Use this tool in these scenarios:
    1. When the user explicitly asks to search for information on the internet.
    2. When the task requires up-to-date or external information not in your knowledge.
    3. When you need to discover relevant webpages before reading their content.
    4. When you want to get some images from internet.

    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. The question can be answered using existing knowledge.
    2. The user already provided specific URLs.
    3. The task requires reading webpage content by url directly.

    ## Important Guidelines
    - The results returned by this tool are only summaries.
    - The images returned by this tool include metadata such as image URLs.
    - Do NOT assume the full content of a webpage based on the title or description.
    - If detailed information is required, call `search_web_by_urls` with the returned URLs.
    - Never fabricate search results or URLs.
    """

    logger.trace('[search_tool.py] [tool] [search_web_by_keywords] Enter')

    client_id = state.get("client_id")
    target_platform = state.get("platform")

    event_writer = ApixStreamWriter()
    event_writer.send_event(
        event=StreamEvent.TOOL_EXEC_START, 
        target_id=client_id, 
        target_platform=target_platform,
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
                "key_word": key_word,
                "provider": provider,
            },
        )

        if not results and not images:
            msg = "No urls and images found, please try other keywords."

            event_writer.send_event(
                event=StreamEvent.TOOL_EXEC_END, 
                target_id=client_id, 
                target_platform=target_platform,
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
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
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
        logger.exception(f"[search_web_by_keywords] failed: {str(e)}")

        error_msg = f"Failed to search web by keyword(s) with error(s): {str(e)}"

        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
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
    

@tool
async def search_web_by_urls(
    urls: str | list[str],
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Fetch and extract the main readable content from one or more webpages.
    The search results are not contain image.

    This tool retrieves and processes webpage content from the provided URLs.
    It extracts the primary textual content of the page for analysis.

    Args:
        urls (str | list[str]): One or more webpage URLs.

    Returns:
        str: Extracted textual content from each webpage.

    ## When to Use This Tool
    Use this tool in these scenarios:
    1. When the user asks to analyze or summarize specific webpages.
    2. When `search_web_by_keywords` returned relevant URLs and you need their full content.
    3. When detailed webpage information is required beyond titles and descriptions.

    ## When NOT to Use This Tool
    Do NOT use this tool when:
    1. You do not have a valid URL.
    2. You only need webpage titles or search results descriptions.
    3. The task does not require reading webpage content.

    ## Important Guidelines
    - Only fetch URLs provided by the user or returned from `search_web_by_keywords`.
    - Never fabricate or guess webpage content.
    - Avoid fetching unnecessary webpages.
    """

    logger.trace('[search_tool.py] [tool] [search_web_by_urls] Enter')

    client_id = state.get("client_id")
    target_platform = state.get("platform")

    event_writer = ApixStreamWriter()
    event_writer.send_event(
        event=StreamEvent.TOOL_EXEC_START, 
        target_id=client_id, 
        target_platform=target_platform,
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
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
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
                event=StreamEvent.TOOL_EXEC_END, 
                target_id=client_id, 
                target_platform=target_platform,
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
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
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
                "provider": provider,
            },
        )

        return Command(update={
            "messages": [
                ToolMessage(result_text, tool_call_id=tool_call_id)
            ]
        })

    except Exception as e:
        logger.exception(f"[search_web_by_urls] failed: {str(e)}")

        error_msg = f"Failed to search web by url(s) with error(s): {str(e)}"

        event_writer.send_event(
            event=StreamEvent.TOOL_EXEC_END, 
            target_id=client_id, 
            target_platform=target_platform,
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