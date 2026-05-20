import copy
import hashlib
from pathlib import Path
import time
from typing import Any, Dict, List, Tuple
import json
import os
from uuid import uuid4
from datetime import datetime, timezone
from collections import deque

from fastapi import HTTPException
import httpx

from langchain_core.messages import SystemMessage, AIMessageChunk, HumanMessage, ToolMessage, AIMessage, AnyMessage

from apix_agent.commons.type_def import MainAgentState, MemoItem
from apix_agent.global_config import BASE_DIR, FILE_SERVICE_URL, MEMORY_SERVICE_BASE_URL
from apix_agent.commons.logger import logger
from apix_agent.commons.file_content_reader import load_from_yaml


class AIContextManager:
    """
    To prepare lang chain Message obj and persist memory to memory module.
    """
    
    # ------------------------------------------------------------------
    # Data related API
    # ------------------------------------------------------------------

    async def append_to_messages(
        self, 
        client_id: str, 
        history_id: str, 
        message: dict,
        parent_id: str = '-',
    ) -> None:
        """
        Append single message to memory service.

        Args:
            client_id: "Id to indicate which user the data is from.",
            history_id: "Id to indicate which history the data belong to.",
            message (dict): Single message dict. Format:
                {
                    "role": "human/ai/system/tools",
                    "content": str,
                    "think": str, // optional
                    "extra": dict, // optional
                    "info": dict, // optional
                    "timestamp": int,
                    "generation_id": str,
                }

        Returns:
            None
        """
        logger.trace('[context_process.py] [AIContextManager] [append_to_messages] Enter')

        if "extra" in message and "user_meta_data" in message["extra"]:
            # file_id and file name should be contained in meta_data list.
            files = message["extra"]["user_meta_data"]
            if files.get("uploaded_files"):
                timestamp = message.get("timestamp", 0)
                generation_id = message.get("generation_id", "")
                sys_message = {
                    "role": "system",
                    "content": f"User upload file(s): {str(files.get("uploaded_files"))}",
                    "timestamp": timestamp,
                    "generation_id": generation_id,
                    "node_id": generation_id[-12:] + "-user",
                    "parent_id": message.get("parent_id") or parent_id
                }
                sys_payload = {
                    "client_id": client_id,
                    "session_id": "",
                    "history_id": history_id,
                    "messages": sys_message,
                }

                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.post(
                        f"{MEMORY_SERVICE_BASE_URL}/memory/memory/append_message",
                        json=sys_payload,
                    )

                if resp.status_code != 200 or not resp.json().get('success'):
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Failed to append memory: {resp.text}",
                    )
                
        generation_id = message.get("generation_id", "")
        role = message.get("role", "")

        if role == 'human': 
            message["node_id"] = generation_id[-12:] + "-user"
            message["parent_id"] = message.get("parent_id") or parent_id
        else:
            message["node_id"] = generation_id[-12:] + "-apix"
            message["parent_id"] = parent_id

        payload = {
            "client_id": client_id,
            "session_id": "",
            "history_id": history_id,
            "messages": message,
        }

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/append_message",
                json=payload,
            )

        if resp.status_code != 200 or not resp.json().get('success'):
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to append memory: {resp.text}",
            )
    

    def _extract_mes_info(
        self, 
        message: AIMessage | AIMessageChunk,
        *,
        fallback_model_provider: str = 'Custom Provider',
        fallback_model_name: str = 'Custom Model',
        fallback_timestamp: int = 0,
    ) -> dict:
        current_timestamp = int(time.time() * 1000)
        if not message.response_metadata:
            message.response_metadata = {}
        message_info = {
            "model_provider": fallback_model_provider or message.response_metadata.get("model_provider", 'Custom Provider'),
            "model": fallback_model_name or message.response_metadata.get("model", 'Custom Model'),
            "total_duration":  current_timestamp - (fallback_timestamp or current_timestamp),
            "total_tokens": (message.usage_metadata or {}).get("total_tokens", 0),
            "id": message.id,
        }
        return message_info
    
    
    async def append_info_message(
        self,
        generation_id: str,
        client_id: str,
        history_id: str,
        timestamp: int,
        additional_info: dict,
        parent_id: str = '-'
    ):
        """
        Append decorated message to memory service (LangChain message -> memory dict).

        This method is a side-effect method and directly writes to memory service.

        Compare to `create_dict_message` (formerly `create_memory`):
        - This method DOES append to memory service internally.
        - This method allows injecting `additional_info` into the message `extra` field.
        - This method is intended for cases where extra runtime/contextual metadata
        needs to be persisted together with the message.
        - Message parsing capability is the same: AIMessage / AIMessageChunk / ToolMessage,
        text content only at present.

        Args:
            client_id: Id to indicate which user the data is from.
            history_id: Id to indicate which history the data belong to.
            message (AIMessage | AIMessageChunk | ToolMessage):
                Message object returned from LangGraph / LLM / Tool node.
            additional_info (dict):
                Extra metadata to be attached to memory message (stored in `extra` field).

        Returns:
            None
        """
        if history_id.startswith("sub_"): return
        logger.trace('[context_process.py] [ ] [create_memory] Enter')
        extra = additional_info
        message = {
            "role": "info", 
            "content": "", 
            "extra": extra, 
            "info": {}, 
            "timestamp": timestamp, 
            "generation_id": generation_id
        }
        await self.append_to_messages(client_id, history_id, message, parent_id)
        
        
    async def update_longterm_memory(self, client_id: str, memorys: dict):
        """
        Insert, modefy or deprecate series of memories to memory service.

        Args:
            client_id: "Id to indicate which user the data is from.",
            memorys (dict): Format:
                {
                    "updates": [
                        {
                            "action": "deprecate",
                            "target_id": "1111-2222",
                            "confidence": 0.96,
                            "reason": "User switched from MySQL to PostgreSQL"
                        },
                        {
                            "action": "insert",
                            "type": "factual",
                            "confidence": 0.95,
                            "content": "User uses PostgreSQL as primary database"
                        },
                        {
                            "action": "modify",
                            "target_id": "3333-4444",
                            "type": "preference",
                            "confidence": 0.94,
                            "content": "User prefers handling locks at the cache layer"
                        }
                    ]
                }

        Returns:
            None
        """
        logger.trace('[context_process.py] [AIContextManager] [append_to_messages] Enter')
        if not memorys: return
        messages = memorys.get('updates', [])
        if not messages: return
        payload = {
            "client_id": client_id,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/update_longterm",
                json=payload,
            )

        if resp.status_code != 200 or not resp.json().get('success'):
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to append memory: {resp.text}",
            )
        
    async def insert_shortterm_memory(self, client_id: str, history_id: str, memory_id: str, content: str):
        """
        Insert shortterm memory to memory service.

        Args:
            client_id: "Id to indicate which user the data is from.",
            history_id: history id,
            memory_id: message's id generated by langChain (task_id in tool massage or id in ai message)
            content: shortterm memory content

        Returns:
            None
        """
        logger.trace('[context_process.py] [AIContextManager] [append_to_messages] Enter')
        content = content.strip()
        if not content: return
        
        payload = {
            "memory_id": memory_id,
            "client_id": client_id,
            "history_id": history_id,
            "content": content
        }

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/insert_shortterm",
                json=payload,
            )

        if resp.status_code != 200 or not resp.json().get('success'):
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to append memory: {resp.text}",
            )
        
    async def fetch_messages(
        self,
        client_id: str,
        history_id: str,
        cursor: int = 0,
        current_node_id: str = '-',
    ) -> tuple[list[dict], str]:
        """
        Fetch messages from memory service.

        Args:
            client_id: Id to indicate which user the data is from.
            history_id: Id to indicate which history the data belong to.
            cursor: Cursor for pagination (reserved).

        Returns:
            list[dict]: Message dict list returned by memory service.
        """
        logger.trace('[context_process.py] [AIContextManager] [fetch_messages] Enter')
        logger.info(
            f"[fetch_messages] client_id={client_id}, history_id={history_id}, cursor={cursor}"
        )
        # msg_cursor = msg_dict.get("msg_cursor", 0)  # reserved

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/messages",
                json={
                    "client_id": client_id,
                    "session_id": "",  # history remains
                    "history_id": history_id,
                    "current_node_id": current_node_id,
                    "cursor": cursor,  # reserved
                },
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to get memory: {resp.text}",
            )

        resp_content = resp.json()
        messages = resp_content.get("messages", [])

        logger.info(f"[fetch_messages] fetched {len(messages)} messages")

        return messages, messages[-1].get('node_id')
        
    async def fetch_summary(
        self,
        client_id: str,
        history_id: str,
    ) -> dict:
        """
        Deprecated Method.
        Fetch messages summary from memory service.

        Args:
            client_id: Id to indicate which user the data is from.
            history_id: Id to indicate which history the data belong to.

        Returns:
            dict: Messages summary dict returned by memory service. Format: 
            {
                "content": "...", // Summarization content.
            }
        """
        logger.trace('[context_process.py] [AIContextManager] [fetch_summary] Enter')
        logger.info(
            f"[fetch_summary] client_id={client_id}, history_id={history_id}"
        )

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/summary",
                json={
                    "client_id": client_id,
                    "history_id": history_id,
                },
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to get summary: {resp.text}",
            )

        resp_content = resp.json()
        messages = resp_content.get("messages", {})

        return messages
        
    async def update_summary(
        self,
        client_id: str,
        history_id: str,
        message: dict
    ):
        """
        Deprecated Method.
        Fetch messages summary from memory service.

        Args:
            client_id: Id to indicate which user the data is from.
            history_id: Id to indicate which history the data belong to.
            message: Dict witn format:
            {
                "content": "...", // Summarization content.
                "message_remains": int, // Message num that not be summarized.
            }
        """
        logger.trace('[context_process.py] [AIContextManager] [update_summary] Enter')
        logger.info(
            f"[update_summary] client_id={client_id}, history_id={history_id}"
        )

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/summary",
                json={
                    "client_id": client_id,
                    "history_id": history_id,
                    "message": message
                },
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to update summary: {resp.text}",
            )

        resp_content = resp.json()
        messages = resp_content.get("messages", {})

        return messages

    async def fetch_longterm_memory(self, client_id: str, count: int = 10, verbose: bool = True) -> list[dict]:
        """
        Fetch longterm memory from memory service.

        Args:
            client_id: Id to indicate which user the data is to get.
            count: How many records will be fetch at most.
            verbose: If return the full dict.

        Returns:
            list[dict]: Memory message dict list returned by memory service. With format 
            [
                {
                    "memory_id": str,
                    "memory_type": str,
                    "content": str,
                    "confidence": float, // if verbose
                    "created_at": str, // if verbose
                    "updated_at": str, // if verbose
                },
                ...
            ]
        """
        logger.trace('[context_process.py] [AIContextManager] [fetch_longterm_memory] Enter')
        logger.info(
            f"[fetch_longterm_memory] client_id={client_id}"
        )

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/longterm",
                json={
                    "client_id": client_id,
                    "count": count,
                },
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to get memory: {resp.text}",
            )

        resp_content = resp.json()
        messages = resp_content.get("messages", []) or []

        return messages

    async def fetch_shortterm_memory(self, client_id: str, history_id: str) -> list[dict]:
        """
        Fetch shortterm memory from memory service.

        Args:
            client_id: Id to indicate which user the data is to get.
            history_id: I do not want to write docsting anymore.

        Returns:
            list[dict]: Memory message dict list returned by memory service. With format 
            [
                {
                    "memory_id": str,
                    "content": str,
                    "created_timestamp": int,
                }
            ]
        """
        logger.trace('[context_process.py] [AIContextManager] [fetch_shortterm_memory] Enter')
        logger.info(
            f"[fetch_shortterm_memory] client_id={client_id} history_id={history_id}"
        )

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/shortterm",
                json={
                    "client_id": client_id,
                    "history_id": history_id,
                },
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to get memory: {resp.text}",
            )

        resp_content = resp.json()
        messages = resp_content.get("messages", []) or []

        return messages
    
    def _ensure_tool_message(self, agent_messages: list[AnyMessage]):
        if not agent_messages:
            return

        cursor = 0
        total_messages = len(agent_messages)

        while cursor < total_messages:
            current_msg = agent_messages[cursor]

            # Only process AI message with tool_calls
            if isinstance(current_msg, (AIMessage, AIMessageChunk)) and getattr(current_msg, "tool_calls", None):
                tool_calls = current_msg.tool_calls or []
                expected_tool_count = len(tool_calls)

                # Scan existing ToolMessages right after this AIMessage
                scan_index = cursor + 1
                existing_tool_count = 0

                while (
                    scan_index < total_messages
                    and isinstance(agent_messages[scan_index], ToolMessage)
                ):
                    existing_tool_count += 1
                    scan_index += 1

                # Calculate how many ToolMessages are missing
                missing_tool_count = expected_tool_count - existing_tool_count

                if missing_tool_count > 0:
                    # Inject missing ToolMessages at the correct position
                    for tool_idx in range(existing_tool_count, expected_tool_count):
                        tool_call = tool_calls[tool_idx]

                        new_msg = ToolMessage(
                            content="[The outputs of this tool have been lost, or the tool's execution was interrupted by the user.]",
                            name=tool_call.get("name"),
                            tool_call_id=tool_call.get("id"),
                        )

                        agent_messages.insert(scan_index, new_msg)
                        scan_index += 1
                        total_messages += 1  # Keep length in sync

                # Move cursor to the end of this AI + Tool block
                cursor = scan_index
            else:
                cursor += 1

    def create_agent_messages(
        self,
        client_messages: list[dict],
        remain_tool_message: bool = True,
        *,
        after_index: str | int = None,
        reasoning: bool = False
    ) -> list[AnyMessage]:
        """
        Create agent messages list (dict list -> LangChain message objects).

        This method is now a pure converter:
        - Only transforms dict messages into LangChain messages

        Args:
            client_messages (list[dict]): Message dict list with format:
                {
                    "generation_id": "uuid4", # Messages generated within the same graph loop share the same generation_id.
                    "role": "human/ai/system/tools",
                    "content": str | list,
                    "extra": dict,   # optional
                    "info": dict,    # optional
                    "timestamp": int
                }
            remain_tool_message (bool): Whether keep tool message.
            after_index: Return only messages after this marker if not None.

        Returns:
            list: List of LangChain message objects
            list: List of LangChain message objects after after_index

        NOTE:
        after_index should equals to msg_dict.get("info").get("id") when its ai message,
        or equals to msg_dict.get("info").get("task_id") when its tool message, but in 
        """
        logger.trace('[context_process.py] [AIContextManager] [create_agent_messages] Enter')
        logger.info(f"[create_agent_messages] client_messages count: {len(client_messages)}, after index: {after_index}")
        # logger.info(f"[create_agent_messages] client_messages: {client_messages}")

        messages = []
        messages_after_index = []
        begin_to_append = not bool(after_index)

        for msg_dict in client_messages:
            id = msg_dict.get("generation_id")
            role = msg_dict.get("role")
            raw_text = msg_dict.get("content", "")
            raw_think = msg_dict.get("think", "")

            if role == "human":
                name = msg_dict.get("name", "user")
                extra = msg_dict.get("extra", {})
                if not isinstance(extra, dict) and extra:
                    extra = json.loads(extra)

                image_data = extra.get("image_data", []) or []
                audio_data = extra.get("audio_data", []) or []
                video_data = extra.get("video_data", []) or []
                file_data  = extra.get("file_data", []) or []

                # Normalize text blocks
                if isinstance(raw_text, str) and raw_text:
                    text_blocks = [{"type": "text", "text": raw_text}]
                elif isinstance(raw_text, list):
                    text_blocks = raw_text
                else:
                    text_blocks = [{"type": "text", "text": str(raw_text)}]

                content = text_blocks + image_data + audio_data + video_data + file_data
                msg = HumanMessage(content=content, name=name)
                messages.append(msg)
                if begin_to_append: messages_after_index.append(msg)

            elif role == "ai":
                info = msg_dict.get("info", {})
                extra = msg_dict.get("extra", {})
                if not isinstance(extra, dict) and extra:
                    extra = json.loads(extra)
                if not isinstance(info, dict) and info:
                    info = json.loads(info)
                index = info.get("id", "")

                content = str(raw_text) if raw_text else ""
                think = str(raw_think if raw_think else "")
                suffix = "[Conversation Abort]"
                if content.endswith(suffix):
                    content = content[:-len(suffix)]
                if think.endswith(suffix):
                    think = think[:-len(suffix)]
                tool_calls = extra.get("tool_calls")
                if (not content and not think) and not remain_tool_message:
                    continue  # Skip empty AI message
                additional_kwargs = {}
                additional_kwargs["reasoning_content"] = think

                msg = AIMessage(
                    id=index,
                    content=content,
                    additional_kwargs=additional_kwargs
                )
                
                if remain_tool_message:
                    if not isinstance(tool_calls, list) and tool_calls:
                        tool_calls = json.loads(tool_calls)
                    msg.tool_calls = tool_calls
                    if not content and not think and tool_calls:
                        called_tools = [call.get("name") for call in (tool_calls or []) if isinstance(call, dict)]
                        inject_content = 'Call tools: ' + ", ".join(called_tools)
                        content = ''
                        additional_kwargs = {}
                        if not reasoning: content = inject_content
                        else: additional_kwargs["reasoning_content"] = inject_content
                        msg = AIMessage(
                            content=content,
                            additional_kwargs=additional_kwargs,
                            tool_calls=tool_calls
                        )

                messages.append(msg)
                if not begin_to_append and index == after_index: 
                    begin_to_append = True
                    continue
                if begin_to_append: messages_after_index.append(msg)

            elif role == "system":
                msg = SystemMessage(content=str(raw_text))
                messages.append(msg)
                if begin_to_append:
                    messages_after_index.append(msg)

            elif role in ("tool", "tools"):
                if not remain_tool_message: continue
                info = msg_dict.get("info", {})
                if not isinstance(info, dict) and info:
                    info = json.loads(info)

                msg = ToolMessage(
                    content=str(raw_text),
                    name=info.get("tool_name"),
                    tool_call_id=info.get("task_id"),
                )
                messages.append(msg)
                if begin_to_append: messages_after_index.append(msg)

            else:
                logger.warning(
                    f"[create_agent_messages] Unknown role or empty content ignored: {role}"
                )

        while messages_after_index and isinstance(messages_after_index[0], ToolMessage):
            messages_after_index.pop(0)

        if after_index and messages_after_index:
            self._ensure_tool_message(messages_after_index)
            return messages_after_index
        self._ensure_tool_message(messages)
        return messages
    
    def create_dict_message(
        self,
        generation_id: str,
        message: AIMessage | AIMessageChunk | ToolMessage | SystemMessage,
        timestamp: int, 
        *,
        fallback_model_provider: str = 'Custom Provider',
        fallback_model_name: str = 'Custom Model',
        fallback_timestamp: int = 0,
        filter: bool = False,
    ) -> dict:
        """
        Create memory dict messages (LangChain message -> dict list).

        This method no longer appends to memory service.
        It only converts LangChain messages into structured dicts.

        Args: 
            filter[bool]: Provide simpler dict message.
            fallback_timestamp[int]: Generation timestamp in second.

        Returns:
            list[dict]: Memory message dicts list (len 1)
        """
        logger.trace('[context_process.py] [AIContextManager] [create_dict_message] Enter')
        logger.info(f"\033[32m[create_dict_message]\033[0m message: {message}")

        messages: dict = {}

        if isinstance(message, (AIMessage, AIMessageChunk)):
            think_content = (message.additional_kwargs or {}).get("reasoning_content", "")
            tool_calls = (message.tool_calls or [])
            extra = {'tool_calls': tool_calls} if tool_calls else {}
            message_info = self._extract_mes_info(message, fallback_model_name=fallback_model_name, fallback_model_provider=fallback_model_provider, fallback_timestamp=fallback_timestamp)

            if filter:
                messages = {
                    "role": "ai",
                    "content": message.content,
                    "think": think_content,
                    "extra": extra,
                }
            else:
                messages = {
                    "role": "ai",
                    "content": message.content,
                    "think": think_content,
                    "extra": extra,
                    "info": message_info,
                    "generation_id": generation_id,
                    "timestamp": timestamp,
                }

        elif isinstance(message, ToolMessage):
            message_info = {
                "tool_name": message.name,
                "task_id": message.tool_call_id,
            }
            content = message.content
            if filter:
                messages = {
                    "role": "tools",
                    "content": content,
                    "info": message_info,
                }
            else:
                messages = {
                    "role": "tools",
                    "content": content,
                    "info": message_info,
                    "generation_id": generation_id,
                    "timestamp": timestamp,
                }

        elif isinstance(message, SystemMessage):
            messages = {
                "role": "system",
                "content": message.content,
                "generation_id": generation_id,
                "timestamp": timestamp,
            }

        else:
            logger.warning(
                f"[create_dict_message] Unsupported message type ignored: {type(message)}"
            )

        return messages
    

    def drop_tool_messages(
        self,
        input_messages: list[AnyMessage],
        *,
        split_by_todos: bool = True,
        min_keep: int = 16
    ) -> list[AnyMessage]:
        """
        Drop tool messages content in input message list.

        Args:
            split_by_todos[bool]: Split by todo item, drop the completed and keep the in_progress.
            min_keep[int]: The min length of the tail that is not to be dropped.
        """

        if not input_messages:
            return input_messages

        n = len(input_messages)

        # Tail protected region start index
        protected_start = max(0, n - min_keep)

        # Step1: find last write_todos
        last_todo_idx = -1

        if split_by_todos:
            for i, msg in enumerate(input_messages):
                # Only check AIMessage with tool_calls
                if isinstance(msg, (AIMessage, AIMessageChunk)):
                    tool_calls = msg.tool_calls
                    if not tool_calls:
                        continue

                    # Check if any tool_call is write_todos
                    for tc in tool_calls:
                        if tc.get("name") == "write_todos":
                            last_todo_idx = i
                            break

        # Step2: process messages
        messages_after_drop = []

        for i, msg in enumerate(input_messages):
            # Keep tail untouched (highest priority)
            if i >= protected_start:
                messages_after_drop.append(msg)
                continue

            # Case1: no split or no write_todos found
            if not split_by_todos or last_todo_idx == -1:
                if isinstance(msg, ToolMessage):
                    # mark outdated
                    new_msg = copy.copy(msg)
                    new_msg.content = "[Tool Result Outdated]"
                    messages_after_drop.append(new_msg)
                else:
                    messages_after_drop.append(msg)
                continue

            # Case2: split_by_todos=True and found last write_todos
            if isinstance(msg, ToolMessage) and i < last_todo_idx:
                new_msg = copy.copy(msg)
                new_msg.content = "[outdated]"
                messages_after_drop.append(new_msg)
            else:
                messages_after_drop.append(msg)

        return messages_after_drop
    
    
    def split_messages(
        self,
        input_messages: list[AnyMessage],
        keep_recent: int = 14,
    ) -> Tuple[list[AnyMessage], list[AnyMessage], list[SystemMessage]]:
        """
        Split messages into:
            - messages to summarize
            - recent messages to keep

        The split point will be adjusted to avoid breaking an
        AIMessage(tool_calls) <-> ToolMessage chain.

        Returns:
            (to_summarize, recent_messages)
        """
        logger.trace('[context_process.py] [AIContextManager] [split_messages] Enter')
        logger.info(
            f"[split_messages] input_messages count: {len(input_messages)}, "
            f"keep_recent={keep_recent}"
        )

        if not input_messages:
            return [], []

        if keep_recent <= 0:
            return input_messages[:], []

        if len(input_messages) <= keep_recent:
            return [], input_messages[:]

        split_idx = len(input_messages) - keep_recent

        while split_idx > 0 and isinstance(input_messages[split_idx], ToolMessage):
            # Find the full tool block that contains split_idx
            tool_start = split_idx
            while tool_start > 0 and isinstance(input_messages[tool_start - 1], ToolMessage):
                tool_start -= 1

            tool_end = split_idx
            while tool_end + 1 < len(input_messages) and isinstance(input_messages[tool_end + 1], ToolMessage):
                tool_end += 1

            prev_idx = tool_start - 1

            if (
                prev_idx >= 0
                and isinstance(input_messages[prev_idx], AIMessage)
                and bool(getattr(input_messages[prev_idx], "tool_calls", None))
            ):
                split_idx = prev_idx
                break

            split_idx = tool_end + 1
            break

        to_summarize = input_messages[:split_idx]
        recent_messages = input_messages[split_idx:]

        logger.info(
            f"[split_messages] result: to_summarize={len(to_summarize)}, "
            f"recent_messages={len(recent_messages)}"
        )

        return to_summarize, recent_messages
    

    def filter_agent_messages(
        self,
        input_messages: list[AnyMessage]
    ) -> tuple[list[AnyMessage], list[AnyMessage], str]:
        """
        Keep only summary-safe messages:
        - HumanMessage
        - AIMessage(content only)

        ToolMessage and AIMessage.tool_calls are dropped.
        SystemMessage will return by a independent message list.

        Return:
            list[AnyMessage]: System message list.
            list[AnyMessage]: AI and human messages after filtered.
            str: message's id
        """
        logger.trace('[context_process.py] [AIContextManager] [filter_agent_messages] Enter')
        logger.info(f"[filter_agent_messages] client_messages count: {len(input_messages)}")

        messages = []
        system_msgs = []
        index = ""

        for input_msg in input_messages:
            content = input_msg.content
            if content is None:
                content = ""

            if isinstance(input_msg, HumanMessage):
                name = input_msg.name
                messages.append(HumanMessage(content=content, name=name))

            elif isinstance(input_msg, AIMessage) or isinstance(input_msg, AIMessageChunk):
                think_content = (input_msg.additional_kwargs or {}).get("reasoning_content", "")
                content = think_content + '\n\n' + content
                msg = AIMessage(content=content)
                index = input_msg.id
                if not content: continue
                messages.append(msg)

            elif isinstance(input_msg, SystemMessage):
                system_msgs.append(copy.copy(input_msg))

        logger.info(f"[filter_agent_messages] The latest message id is {index}")
        return system_msgs, messages, index
        

    async def fetch_available_documents(self, client_id: str) -> list:
        """
        Get the documents metadata from file service.

        Returns: list [
            {
                "document_id": str,
                "document_name": str,
                "document_description": str,
                "embed_engine": list,
                "mime_type": str,
                "document_size": int,
                "is_active": bool,
                "upload_at": str,
            },
            ...
        ]
        """
        try:
            payload = {
                "client_id": client_id,
                "limit": 999,
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{FILE_SERVICE_URL}/file/rag/get_available_documents",
                    json=payload,
                )
                data = resp.json()
        except Exception:
            return []

        if not data.get("success"):
            return []

        documents = data.get("messages", [])

        visible_documents = []
        for document in documents:
            if document.get("is_active"):
                visible_documents.append(document)

        return visible_documents

    async def fetch_available_skills(self, client_id: str) -> list:
        """
        Get the skills metadata from file service.

        Returns: list [
            {
                "skill_id": str,
                "skill_name": str,
                "skill_description": str,
                "skill_version": str,
                "package_size": int,
                "is_active": bool,
                "upload_at": str,
            },
            ...
        ]
        """
        try:
            payload = {
                "client_id": client_id,
                "limit": 999
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                        f"{FILE_SERVICE_URL}/file/skills/get_available_skills",
                        json=payload,
                    )
                data = resp.json()
        except Exception:
            return []

        if not data.get("success"):
            return []

        skills = data.get("messages", [])

        visible_skills = []
        for skill in skills:
            if skill.get("is_active"):
                visible_skills.append(skill)

        return visible_skills
    
    def init_memorandum_list(self, state: MainAgentState):
        client_id = state.get("client_id", "")
        history_id = state.get("history_id", "")
        workspace = state.get("config", {}).get("work_dir")

        memo_namespace = client_id + ":" + (workspace or history_id) + ":" + state.get("agent_role")
        fallback_memo_namespace = client_id + ":" + history_id + ":" + state.get("agent_role")

        memo_dir = Path(BASE_DIR) / "memo"

        def load_memories(namespace: str) -> list[MemoItem]:
            hash_input = namespace.encode("utf-8")
            memo_filename = hashlib.sha256(hash_input).hexdigest()
            memo_path = memo_dir / f"{memo_filename}.yaml"

            logger.info(f"[init_memorandum_list] Trying to load memorandum_list from {memo_path}")

            if not memo_path.exists():
                return []

            memorandum_list = load_from_yaml(memo_path) or []

            if not isinstance(memorandum_list, list):
                logger.warning(
                    f"[init_memorandum_list] Invalid memorandum yaml structure for client_id {client_id}: {memorandum_list}"
                )
                return []

            return memorandum_list

        merged_memorandum_map = {}

        for memo in load_memories(memo_namespace):
            title = memo.get("title")
            if title:
                merged_memorandum_map[title] = memo

        if memo_namespace != fallback_memo_namespace:
            for memo in load_memories(fallback_memo_namespace):
                title = memo.get("title")

                if not title:
                    continue

                existing = merged_memorandum_map.get(title)

                # Keep newer memo with same title
                if existing is None or memo.get("date", "") > existing.get("date", ""):
                    merged_memorandum_map[title] = memo

        memorandum_list = list(merged_memorandum_map.values())

        logger.info(
            f"[init_memorandum_list] Initialized memorandum list for client_id {client_id}, "
            f"history_id {history_id}: {memorandum_list}"
        )

        state["memorandum"].clear()
        state["memorandum"].extend(memorandum_list)
        
    # Runtime prompt
    def create_skills_prompt(self, state: MainAgentState, agent_role: str = None) -> str:
        """
        Build the skills index prompt for the agent.

        This only exposes skills name and descriptions.
        The agent must explicitly load a skill package when needed.
        """
        skills = state.get("skills", [])

        if not skills:
            return "## No Available Skills.\n\n"

        lines = []

        lines.append("## Available Skills\n")

        lines.append(
            "Skills are reusable capability packages that help you perform complex tasks. "
            "Each skill contains detailed instructions and examples describing how to use it."
        )

        lines.append(
            "Before using a skill, you must load it using the `load_skill` tool. "
            "This will provide the skill's guide (SKILL.md), which explains how the skill works "
            "and how to use it correctly.\n"
        )

        lines.append(
            "Only load a skill if it is clearly relevant to the user's request. "
            "Do not load unnecessary skills.\n"
        )

        lines.append("### Available skills to load:\n")

        for skill in skills:
            name = skill.get("skill_name", "").strip()
            desc = skill.get("skill_description", "").strip()

            if not name:
                continue

            lines.append(f"- {name}")
            if desc:
                lines.append(f"  Description: {desc}")
            lines.append("")

        lines.append(
            "If you determine that a skill is required, call the `load_skill` tool with the skill name. "
            "After loading the skill, follow the instructions provided in its guide."
        )

        return "\n".join(lines) + "\n\n"
        
    # Runtime prompt
    def create_documents_prompt(self, state: MainAgentState, agent_role: str = None) -> str:
        """
        Build the documents index prompt for the agent.

        This prompt only exposes document names and descriptions.
        The agent may use these documents as candidates for knowledge base retrieval.
        """
        documents = state.get("documents", [])

        if not documents:
            return "## No Available Documents In Knowledge Base.\n\n"

        lines = []

        lines.append("## Available Documents\n")

        lines.append(
            "These documents are available for knowledge base retrieval. "
            "Each document includes a name and an optional description to help you decide "
            "whether it is relevant to the user's request."
        )

        lines.append(
            "Use these documents to identify which document IDs should be passed to the "
            "`knowledge_base_retrieval` tool."
        )

        lines.append(
            "Only select documents that are clearly relevant to the user's request. "
            "Do not include unnecessary documents.\n"
        )

        lines.append("### Available documents for knowledge base retrieval:\n")

        for document in documents:
            name = document.get("document_name", "").strip()
            desc = document.get("document_description", "").strip()
            document_id = document.get("document_id", "").strip()

            if not name:
                continue

            if document_id:
                lines.append(f"- {name} (document_id: {document_id})")
            else:
                lines.append(f"- {name}")

            if desc:
                lines.append(f"  Description: {desc}")
            lines.append("")

        lines.append(
            "When needed, call the `knowledge_base_retrieval` tool with the user's query and "
            "the selected document IDs to retrieve relevant document chunks."
        )

        return "\n".join(lines) + "\n\n"
    
    # Before graph rule prompt
    def create_workflow_prompt(self, state: MainAgentState, agent_role: str = None) -> str:
        config = state.get("config", {})
        enable_think = bool(config.get("enable_think", False))

        if not enable_think:
            return ""
        
        if agent_role in ["agent", "sub_agent", "team_worker"]:
            steps = [
                "### Understand\nCarefully read the user's request, determine the real objective."
            ]
            steps.append(
                "### Think\nReason about the problem before taking action and break it into logical steps."
            )
            steps.append(
                "### Load Knowledge\nLoad and review relevant skills if they may help solve the task."
            )
            steps.append(
                "### Plan\nGenerate todos to structure the work if the task involves multiple steps."
            )
            steps.append(
                "### Act\nSolve the task step by step, using available tools when necessary."
            )
            steps.append(
                "### Verify\nCheck intermediate results to ensure they match the user's request."
            )
            guidelines = """
## General Guidelines

- Do not skip planning for complex tasks.
- Use tools only when necessary.
- Never assume tool results.
- Prefer incremental progress over large uncertain actions.
- Append your operation logs and important events to /workspace/sub_agent_bus.log.
"""
            return (
                "# Follow this workflow when solving the task:\n\n"
                + "\n\n".join(f"## Step {i+1}\n{step}" for i, step in enumerate(steps))
                + "\n\n"
                + guidelines
                + "\n\n"
            )
        
        elif agent_role == 'main_agent':
            steps = [
                "### Understand\nCarefully read the user's request and determine the real objective."
            ]
            steps.append(
                "### Assign\nDelegation task to a sub-agent, create one clear and self-contained task for a single sub-agent."
            )
            steps.append(
                "### Feedback\nDo not wait for the task result and briefly inform the user whether the task was delegated."
            )
            guidelines = """
## General Guidelines

- Do not delegate simple task, Never handle complex task youself.
- Assign at most one sub-agent task per user request.
- Ensure instructions for the sub-agent are self-contained.
- Prefer clear task goals and precise instructions when delegating.
"""

            return (
                "# Follow this workflow when solving the task:\n\n"
                + "\n\n".join(f"## Step {i+1}\n{step}" for i, step in enumerate(steps))
                + "\n\n"
                + guidelines
                + "\n\n"
            )
        
        elif agent_role == 'team_leader':
            steps = [
                "### Clarify the request\n"
                "Understand the user's objective and ask for clarification if any requirement is unclear."
            ]

            steps.append(
                "### Decompose the task\n"
                "Break the task into **several relatively independent sub-tasks**. Each sub-task should define a certain goal."
            )

            steps.append(
                "### Maintain a TODO list\n"
                "Represent each sub-task as a TODO item.\n\n"
                "* When a sub-task is assigned → mark TODO as **in progress**\n"
                "* When the sub-task is finished → mark TODO as **completed**"
            )

            steps.append(
                "### Delegate sub-tasks\n"
                "Assign each sub-task to a suitable sub-agent and clearly describe the goal and expected outputs. "
                "Sub-agents should only work on the assigned task."
            )

            steps.append(
                "### Non-blocking coordination\n"
                "Sub-agent tasks may take a long time. Do not wait for tasks to finish. "
                "Inform the user about the plan, task breakdown, and current TODO status."
            )

            guidelines = """
## General Guidelines

- Never handle complex task yourself, assign sub-agents to handle.
- Do not assign a sub-agent for each simple task, combine them into one task.
- Ensure instructions for the sub-agent are self-contained.
- Prefer clear task goals and precise instructions when delegating.
- Always ask the user for clarification instead of making assumptions.
        """

            return (
                "# Team Leader Workflow\n\n"
                "Follow this workflow when solving the task:\n\n"
                + "\n\n".join(f"## Step {i+1}\n{step}" for i, step in enumerate(steps))
                + "\n\n"
                + guidelines
                + "\n\n"
            )


    # Brfore graph prompt
    def create_memory_prompt(self, messages: list[dict]) -> str:
        '''
        Create a human-like message that softly provides long-term context,
        without exposing system structure, timestamps, or internal records.

        Args:
            messages (list[dict]): List of memory messages.
        '''

        # --- build human-readable memory impressions ---
        impressions: list[str] = []

        # Current time anchor (used only for relative comparison)
        now = datetime.now(timezone.utc)

        for msg in messages:
            content = msg.get("content")
            if not content:
                continue

            memory_type = msg.get("memory_type", "")
            updated_ts = msg.get("updated_timestamp")

            # --- build vague relative time description (no numbers) ---
            time_hint = ""
            if isinstance(updated_ts, (int, float)):
                try:
                    ts_s = updated_ts / 1_000_000.0
                    then = datetime.fromtimestamp(ts_s, timezone.utc)
                    delta_seconds = (now - then).total_seconds()

                    day = 24 * 3600
                    week = 7 * day
                    month = 30 * day

                    if delta_seconds < day:
                        time_hint = "today"
                    elif delta_seconds < week:
                        time_hint = "a few days ago"
                    elif delta_seconds < month:
                        time_hint = "several weeks ago"
                    else:
                        time_hint = "months ago"
                except Exception:
                    time_hint = ""

            content = content.strip()

            # --- align time wording with memory_type semantics ---
            if not time_hint:
                impressions.append(content)

            elif memory_type in ("fact", "rule"):
                # Stable memories: never imply expiration
                impressions.append(
                    f"{content} — noted {time_hint}."
                )

            elif memory_type == "preference":
                # Preferences may change, but should not be assumed expired
                impressions.append(
                    f"{content} — noted {time_hint}."
                )

            elif memory_type in ("event", "transient"):
                # Time-sensitive memories: time is part of the meaning
                impressions.append(
                    f"{time_hint.capitalize()}, {content}"
                )

            else:
                # Safe fallback
                impressions.append(
                    f"{content} — noted {time_hint}."
                )

        if not impressions:
            logger.info("[create_memory_prompt] no longterm memory found")
            return ""

        # --- merge into a natural, markdown-structured context ---
        memory = (
            "## Long-term Context\n\n"
            "The following background information may be helpful:\n\n"
            + "\n".join(f"- {i}" for i in impressions)
            + "\n\nAs of today."
        )

        return memory + "\n\n"
    
    # Runtime prompt
    def create_shortterm_prompt(self, messages: list[dict]) -> str:
        '''
        Create a human-like message that softly provides long-term context,
        without exposing system structure, timestamps, or internal records.

        Args:
            messages (list[dict]): List of memory messages.
        '''
        if not messages: return ""
        content = messages[0].get("content", "")
        if not content: return ""
        memory = (
            "## Short-term Context\n\n"
            "The following is a summary of earlier messages in this conversation.:\n\n"
            + content
        )
        return memory
    
    # Runtime prompt
    def create_workspace_prompt(
        self,
        state: MainAgentState,
        agent_role: str = None
    ) -> str:
        work_dir = state.get("work_dir", "")
        sandbox = state.get("sandbox", "")
        config = state.get("config", {})
        no_sandbox = bool(config.get("no_sandbox", False))

        if not work_dir:
            return "## No work_dir has been specified by the user.\n\n"

        if not os.path.exists(work_dir):
            return (
                "## Error: The configured work_dir path does not exist on the filesystem. "
                "Please ask the user to configure a valid existing directory.\n\n"
            )

        if no_sandbox:
            prompt = f"## Your workspace is {work_dir}"
        elif sandbox:
            prompt = "## [Ubuntu] Sandbox has been configured. \n- The user will share access to this sandbox with you."
        else:
            prompt = "## Sandbox configure failed."

        return f"{prompt}\n\n"

    # Runtime prompt
    def create_todo_prompt(self, state: MainAgentState, agent_role: str = None) -> str:
        todo_list = state.get("todos", [])
        if not todo_list:
            # return "## Todo list is empty or outdate.\n\n"
            return ""

        lines = ["## Current Todo List:"]
        if agent_role == "team_leader":
            lines = ["## Task Progress:"]

        for index, item in enumerate(todo_list, start=1):
            lines.append(f"{index}. {item['content']}--{item['status']};")

        formatted = "\n".join(lines)

        return formatted + "\n\n"

    # Runtime prompt
    def create_memorandum_prompt(self, state: MainAgentState, agent_role: str = None) -> str:
        memorandum_list: List[MemoItem] = state.get("memorandum", [])

        if not memorandum_list:
            return "## No memories available.\n\n"

        lines = ["## Available Memories:"]

        for index, item in enumerate(memorandum_list, start=1):
            title = item.get("title", "").strip()
            date = item.get("date", "").strip()

            lines.append(
                f"{index}. title: {title} | date: {date}"
            )

        return "\n".join(lines) + "\n\n"

    
    def create_system_prompt_list(self, state: MainAgentState, agent_role: str = None):
        blocks = []

        # 1. Rules
        blocks.append(SystemMessage(content=(state.get("rule_prompt", "") + "\n\n" + self.create_workflow_prompt(state, agent_role))))
        # 2. Longterm memory
        if state.get("longterm_memory"):
            blocks.append(SystemMessage(
                content="# [LONGTERM MEMORY]\n" + (state["longterm_memory"] or "None")
            ))
        # 3. Shortterm summary
        if state.get("shortterm_memory"):
            blocks.append(SystemMessage(
                content="# [RECENT SUMMARY / SHORT-TERM MEMORY]\n" + (state["shortterm_memory"] or "None")
            ))
        # 4. Runtime
        if state.get("runtime_prompt"):
            blocks.append(SystemMessage(
                content="# [RUNTIME STATE]\n" + (state["runtime_prompt"] or "None")
            ))

        return blocks

    
    def create_role_prompt_list(self, state: MainAgentState, agent_role: str = None):
        prompt = state["config"].get("role_prompt", {})
        higher_role_prompt_permission = state["config"].get("higher_role_prompt_permission", False)
        name = prompt.get("name", "") or state.get("agent_name")
        definition = prompt.get("definition", "") or agent_role
        if not definition.strip() and not name.strip():
            return []
        
        structured = "# [ROLE DEFINITION]\n"
        if name.strip():
            structured += f"- Your name is {name.strip()}.\n"
        if definition.strip():
            structured += f"- Your Characteristics:\n {definition.strip()}\n"

        logger.info(f"[create_role_prompt_list] Insert role prompt:\n{structured}")
        if not higher_role_prompt_permission: return [HumanMessage(content=structured)]
        else: return [SystemMessage(content=structured)]



ai_context_manager = AIContextManager()
