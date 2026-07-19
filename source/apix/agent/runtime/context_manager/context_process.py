import copy
import hashlib
from pathlib import Path
import time
from typing import List, Tuple
import json
import os

from fastapi import HTTPException
import httpx

from apix.agent.common.state import MainAgentState
from apix.common.utils.yaml import load_from_yaml
from apix.agent.common.message import AiMessage, AiMessageChunk, ToolMessage, SystemMessage, UserMessage, InfoMessage, AnyMessage
from apix.common.utils.trans import convert_generation_id_to_message_node_id
from apix.agent.common.type import MemoItem
from apix.config.base_config import BASE_DIR, BASE_URL
from apix.common.utils.logger import logger


class AIContextManager:
    """
    To prepare lang chain Message obj and persist memory to memory module.
    """
    
    # ------------------------------------------------------------------
    # Data related API
    # ------------------------------------------------------------------

    async def append_to_messages(
        self, 
        user_uid: str, 
        conversation_uid: str, 
        message: dict,
        parent_id: str = '-',
    ) -> None:
        """
        Append single message to memory service.

        Args:
            user_uid: user id,
            conversation_uid: conversation id,
            message (dict): Single message dict. Format:
                {
                    "role": str,
                    "content": str,
                    "think": str, # optional
                    "extra": dict, # optional
                    "info": dict, # optional
                    "timestamp": int,
                    "generation_id": str,
                }

        Returns:
            None
        """
        logger.trace()
        if conversation_uid.startswith("sub_"): return

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
                    "node_id": convert_generation_id_to_message_node_id(generation_id, 'user'),
                    "parent_id": message.get("parent_id") or parent_id
                }
                sys_payload = {
                    "user_uid": user_uid,
                    "conversation_uid": conversation_uid,
                    "messages": sys_message,
                }

                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.post(
                        f"{BASE_URL}/memory/append_message",
                        json=sys_payload,
                    )

                if resp.status_code != 200 or not resp.json().get('success'):
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"Failed to append memory: {resp.text}",
                    )
                
        generation_id = message.get("generation_id", "")
        role = message.get("role", "")
        message["node_id"] = convert_generation_id_to_message_node_id(generation_id, role)

        if role == 'user': 
            message["parent_id"] = message.get("parent_id") or parent_id
        else:
            message["parent_id"] = parent_id

        payload = {
            "user_uid": user_uid,
            "conversation_uid": conversation_uid,
            "messages": message,
        }

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{BASE_URL}/memory/append_message",
                json=payload,
            )

        if resp.status_code != 200 or not resp.json().get('success'):
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to append memory: {resp.text}",
            )
    

    def _extract_mes_info(
        self, 
        message: AiMessage | AiMessageChunk,
        *,
        fallback_model_provider: str = 'Custom Provider',
        fallback_model_name: str = 'Custom Model',
    ) -> dict:
        if not message.info:
            message.info = {}
        message_info = {
            "provider":  message.info.get("provider", fallback_model_provider),
            "model":  message.info.get("model", fallback_model_name),
            "duration":  message.info.get("duration", -1),
            "tokens": message.info.get("tokens", -1),
            "id": message.id,
        }
        return message_info
    
    
    async def append_info_message(
        self,
        generation_id: str,
        user_uid: str,
        conversation_uid: str,
        timestamp: int,
        additional_info: dict,
        parent_id: str = '-'
    ):
        """
        Append an info message to memory service.

        Args:
            generation_id: 
            user_uid: user id.
            conversation_uid: conversation id.
            timestamp: ISO8601 timestamp.
            additional_info: Extra metadata to be attached to memory message (stored in `extra` field).
            parent_id: parent message node's id.

        Returns:
            None
        """
        if conversation_uid.startswith("sub_"): return
        logger.trace()
        extra = additional_info
        message = {
            "role": "info", 
            "content": "", 
            "extra": extra, 
            "info": {}, 
            "timestamp": timestamp, 
            "generation_id": generation_id
        }
        await self.append_to_messages(user_uid, conversation_uid, message, parent_id)

        
    async def insert_shortterm_memory(self, user_uid: str, conversation_uid: str, memory_id: str, content: str):
        """
        Insert shortterm memory to memory service.

        Args:
            user_uid: "Id to indicate which user the data is from.",
            conversation_uid: history id,
            memory_id: message's id generated by langChain (task_id in tool massage or id in ai message)
            content: shortterm memory content

        Returns:
            None
        """
        logger.trace()
        content = content.strip()
        if not content: return
        
        payload = {
            "memory_id": memory_id,
            "user_uid": user_uid,
            "conversation_uid": conversation_uid,
            "content": content
        }

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/insert_shortterm",
                json=payload,
            )

        if resp.status_code != 200 or not resp.json().get('success'):
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to append memory: {resp.text}",
            )
        
        
    async def fetch_messages(
        self,
        user_uid: str,
        conversation_uid: str,
        cursor: int = 0,
        current_node_id: str = '-',
    ) -> tuple[list[dict], str]:
        """
        Fetch messages from memory service.

        Args:
            user_uid: Id to indicate which user the data is from.
            conversation_uid: Id to indicate which history the data belong to.
            cursor: Cursor for pagination (reserved).

        Returns:
            list[dict]: Message dict list returned by memory service.
        """
        logger.trace()
        logger.info(
            f"user_uid={user_uid}, conversation_uid={conversation_uid}, cursor={cursor}"
        )
        # msg_cursor = msg_dict.get("msg_cursor", 0)  # reserved

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/messages",
                json={
                    "user_uid": user_uid,
                    "conversation_uid": conversation_uid,
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

        logger.info(f"Fetched {len(messages)} messages")

        return messages, messages[-1].get('node_id')
    

    async def fetch_shortterm_memory(self, user_uid: str, conversation_uid: str) -> list[dict]:
        """
        Fetch shortterm memory from memory service.

        Args:
            user_uid: Id to indicate which user the data is to get.
            conversation_uid: I do not want to write docsting anymore.

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
        logger.trace()
        logger.info(
            f"user_uid={user_uid}, conversation_uid={conversation_uid}"
        )

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MEMORY_SERVICE_BASE_URL}/memory/memory/shortterm",
                json={
                    "user_uid": user_uid,
                    "conversation_uid": conversation_uid,
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
            if isinstance(current_msg, (AiMessage, AiMessageChunk)) and getattr(current_msg, "tool_calls", None):
                tool_calls = current_msg.tool_calls or []
                expected_tool_count = len(tool_calls)

                # Scan existing ToolMessages right after this AiMessage
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
                    "role": str,
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
        logger.trace()
        logger.info(f"client_messages count: {len(client_messages)}, after index: {after_index}")
        # logger.info(f"client_messages: {client_messages}")

        messages = []
        messages_after_index = []
        begin_to_append = not bool(after_index)

        for msg_dict in client_messages:
            id = msg_dict.get("generation_id")
            role = msg_dict.get("role")
            raw_text = msg_dict.get("content", "")
            raw_think = msg_dict.get("think", "")

            if role == "user":
                name = msg_dict.get("name", "user")
                extra = msg_dict.get("extra", {})
                if not isinstance(extra, dict) and extra:
                    extra = json.loads(extra)

                active_file = extra.get("active_file", '') or ''
                referenced_message = extra.get("referenced_message", {}) or {}
                system_instruction = extra.get("system_instruction", []) or []

                if referenced_message and isinstance(referenced_message, dict):
                    raw_text = f"Referenced Message:  \n" \
                        f"> Role: {referenced_message.get("role", "`[unknow]`") or '`[unknow]`'}  " \
                        f"Content: \"{referenced_message.get("content", "`[content missed]`") or '`[content missed]`'}\""\
                        f"\n\n{raw_text}"
                    
                if active_file:
                    raw_text = f"Referenced File:  \n> \"{active_file}\"\n\n{raw_text}"

                if system_instruction and isinstance(system_instruction, dict):
                    raw_text = f"System Instruction:  \n \"{'\n-'.join(system_instruction.get('prompt', []))}\"\n\n{raw_text}"

                msg = UserMessage(content=raw_text, name=name)
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

                msg = AiMessage(
                    id=index,
                    content=content,
                    additional_kwargs=additional_kwargs
                )
                
                if remain_tool_message:
                    if not isinstance(tool_calls, list) and tool_calls:
                        tool_calls = json.loads(tool_calls)
                    if tool_calls:
                        msg.tool_calls = tool_calls

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

            elif role == "tool":
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
                logger.warning(f"Unknown role or empty content ignored: {role}")

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
        message: AiMessage | AiMessageChunk | ToolMessage | SystemMessage,
        timestamp: int, 
        *,
        fallback_model_provider: str = 'Custom Provider',
        fallback_model_name: str = 'Custom Model',
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
        logger.trace()
        messages: dict = {}

        if isinstance(message, (AiMessage, AiMessageChunk)):
            think_content = (message.additional_kwargs or {}).get("reasoning_content", "")
            tool_calls = (message.tool_calls or [])
            extra = {'tool_calls': tool_calls} if tool_calls else {}
            message_info = self._extract_mes_info(message, fallback_model_name=fallback_model_name, fallback_model_provider=fallback_model_provider)

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
            content = str(message.content)
            if filter:
                messages = {
                    "role": "tool",
                    "content": content,
                    "info": message_info,
                }
            else:
                messages = {
                    "role": "tool",
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
                f"Unsupported message type ignored: {type(message)}"
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
                # Only check AiMessage with tool_calls
                if isinstance(msg, (AiMessage, AiMessageChunk)):
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
        AiMessage(tool_calls) <-> ToolMessage chain.

        Returns:
            (to_summarize, recent_messages)
        """
        logger.trace()
        logger.info(
            f"Input messages length: {len(input_messages)}, "
            f"Base keep recent={keep_recent}"
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
                and isinstance(input_messages[prev_idx], AiMessage)
                and bool(getattr(input_messages[prev_idx], "tool_calls", None))
            ):
                split_idx = prev_idx
                break

            split_idx = tool_end + 1
            break

        to_summarize = input_messages[:split_idx]
        recent_messages = input_messages[split_idx:]

        logger.info(
            f"Result: to_summarize={len(to_summarize)}, "
            f"recent_messages={len(recent_messages)}"
        )

        return to_summarize, recent_messages
    

    def filter_agent_messages(
        self,
        input_messages: list[AnyMessage]
    ) -> tuple[list[AnyMessage], list[AnyMessage], str]:
        """
        Keep only summary-safe messages:
        - UserMessage
        - AiMessage(content only)

        ToolMessage and AiMessage.tool_calls are dropped.
        SystemMessage will return by a independent message list.

        Return:
            list[AnyMessage]: System message list.
            list[AnyMessage]: AI and user messages after filtered.
            str: message's id
        """
        logger.trace()
        logger.info(f"Client messages count: {len(input_messages)}")

        messages = []
        system_msgs = []
        index = ""

        for input_msg in input_messages:
            content = input_msg.content
            if content is None:
                content = ""

            if isinstance(input_msg, UserMessage):
                name = input_msg.name
                messages.append(UserMessage(content=content, name=name))

            elif isinstance(input_msg, AiMessage) or isinstance(input_msg, AiMessageChunk):
                think_content = (input_msg.additional_kwargs or {}).get("reasoning_content", "")
                content = think_content + '\n\n' + content
                msg = AiMessage(content=content)
                index = input_msg.id
                if not content: continue
                messages.append(msg)

            elif isinstance(input_msg, SystemMessage):
                system_msgs.append(copy.copy(input_msg))

        logger.info(f"The latest message id is {index}")
        return system_msgs, messages, index
        

    async def fetch_available_documents(self, user_uid: str) -> list:
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
                "user_uid": user_uid,
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

    async def fetch_available_skills(self, user_uid: str) -> list:
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
                "user_uid": user_uid,
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
        user_uid = state.get("user_uid", "")
        conversation_uid = state.get("conversation_uid", "")
        workspace = state.get("config", {}).get("work_dir")

        memo_namespace = user_uid + ":" + (workspace or conversation_uid) + ":" + state.get("agent_role")
        fallback_memo_namespace = user_uid + ":" + conversation_uid + ":" + state.get("agent_role")

        memo_dir = Path(BASE_DIR) / "memo"

        def load_memories(namespace: str) -> list[MemoItem]:
            hash_input = namespace.encode("utf-8")
            memo_filename = hashlib.sha256(hash_input).hexdigest()
            memo_path = memo_dir / f"{memo_filename}.yaml"

            logger.info(f"Trying to load memorandum list from {memo_path}")

            if not memo_path.exists():
                return []

            memorandum_list = load_from_yaml(memo_path) or []

            if not isinstance(memorandum_list, list):
                logger.warning(
                    f"Invalid memorandum yaml structure for client {user_uid}: {memorandum_list}"
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
            f"Initialized memorandum list for client {user_uid}, "
            f"conversation {conversation_uid}: {memorandum_list}"
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
        
    
    # Runtime prompt
    def create_shortterm_prompt(self, messages: list[dict]) -> str:
        '''
        Create a user-like message that softly provides long-term context,
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
        sandbox = state.get("sandbox", "")
        config = state.get("config", {})
        work_dir = config.get("work_dir", "")

        if not work_dir:
            return "## No workspace directory has been specified by the user.\n\n"

        if not os.path.exists(work_dir):
            raise FileNotFoundError(f"Workspace directory does not exist: {work_dir}")

        if not sandbox:
            return "## Sandbox configuration failed.\n\n"

        return f"""## Sandbox Environment

An Ubuntu sandbox is available and shared with the user.

Workspace mapping:
{work_dir} → /workspace

Rules:
- Use `/workspace` as the workspace root inside the sandbox.
- Prefer relative paths in project code file whenever possible.
- Never expose `/workspace` in user-facing responses.
- When showing file paths to the user, always use `{work_dir}`.

Examples:

Sandbox usage:
- Read file: /workspace/data/input.csv
- Write file: /workspace/output/report.pdf
- Preferred in project code: open("data/input.csv")

User-facing output:
- Show image in Markdown: ![Image]({work_dir}/images/result.png)
- Report output file: File saved to: {work_dir}/report.pdf
"""
    

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
    def create_memorandum_prompt(
        self,
        state: MainAgentState,
        agent_role: str = None,
    ) -> str:
        memorandum_list: List[MemoItem] = state.get("memorandum", [])

        if not memorandum_list:
            return "## No memories available.\n\n"

        lines = [
            "## Available Memories:\n",
            "| # | Title | Date | Abstract |",
            "|---|---|---|---|",
        ]

        for index, item in enumerate(memorandum_list, start=1):

            title = item.get("title", "").strip()
            date = item.get("date", "").strip()
            abstract = item.get("abstract", "").strip()

            # Escape markdown table separators
            title = title.replace("|", "\\|")
            abstract = abstract.replace("|", "\\|")

            lines.append(
                f"| {index} | {title} | {date} | {abstract or 'None'} |"
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

        logger.info(f"Insert role prompt:\n{structured}")
        if not higher_role_prompt_permission: return [UserMessage(content=structured)]
        else: return [SystemMessage(content=structured)]



ai_context_manager = AIContextManager()
