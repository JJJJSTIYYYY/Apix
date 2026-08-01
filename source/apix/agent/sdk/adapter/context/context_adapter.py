import copy
from typing import List, Tuple
import json
import os
from typing import Any
from xml.sax.saxutils import escape

from apix.agent.sdk.utils.message import ApixMessageBase, ApixSystemMessage, ApixAiMessageChunk, ApixUserMessage, ApixToolMessage, ApixAiMessage, AnyMessage
from apix.agent.sdk.utils.funcs import convert_generation_id_to_message_node_id
from apix.agent.sdk.graph.state import MainAgentState, LongtermMemory, Skill, Todo
from apix.common.utils.logger import logger


class AIContextAdapter:
    """Context adapter for agent sdk.
    """

    _MISSING_TOOL_OUTPUT = (
        "[The outputs of this tool have been lost, or the tool's execution was interrupted by the user.]"
    )

    def _build_user_context(
        self,
        extensions: dict[str, Any],
        todo: list[Todo] = None,
    ) -> str:
        context_parts: list[str] = []

        referenced_message = extensions.get("referenced_message") or {}
        if isinstance(referenced_message, dict) and referenced_message:
            referenced_role = referenced_message.get("role") or "[UNKNOWN]"
            referenced_speaker = referenced_message.get("name") or "[UNKNOWN]"
            referenced_content = (
                referenced_message.get("content")
                or "[CONTENT MISSED]"
            )

            context_parts.append(
                "<referenced_message>\n"
                f"  <role>{escape(str(referenced_role))}</role>\n"
                f"  <speaker>{escape(str(referenced_speaker))}</speaker>\n"
                f"  <content>{escape(str(referenced_content))}</content>\n"
                "</referenced_message>"
            )

        active_file = extensions.get("active_file") or ""
        if active_file:
            context_parts.append(
                f"<active_file>{escape(str(active_file))}</active_file>"
            )

        uploaded_files = extensions.get("uploaded_files") or []
        if isinstance(uploaded_files, list) and uploaded_files:
            files_xml = "\n".join(
                f"  <file>{escape(f'./upload_files/{filename}')}</file>"
                for filename in uploaded_files
            )

            context_parts.append(
                "<uploaded_files>\n"
                f"{files_xml}\n"
                "</uploaded_files>"
            )

        if todo:
            todo_list = []
            for index, item in enumerate(todo, start=1):
                todo_list.append(f"{index}. {item['content']}--{item['status']};")
            todo_list = "\n".join(todo_list)
            context_parts.append(
                "<todo_list>\n"
                f"{todo_list}\n"
                "</todo_list>"
            )

        task = extensions.get("task") or {}
        if isinstance(task, dict) and task:
            task_type = task.get("type")
            task_name = task.get("name")
            task_prompt = task.get("prompt")

            task_parts: list[str] = []

            if task_type:
                task_parts.append(
                    f"  <type>{escape(str(task_type))}</type>"
                )

            if task_name:
                task_parts.append(
                    f"  <name>{escape(str(task_name))}</name>"
                )

            if task_prompt:
                task_parts.append(
                    f"  <prompt>{escape(str(task_prompt))}</prompt>"
                )

            if task_parts:
                context_parts.append(
                    "<task>\n"
                    f"{'\n'.join(task_parts)}\n"
                    "</task>"
                )

        if not context_parts:
            return ""

        return (
            "<context>\n"
            f"{'\n\n'.join(context_parts)}\n"
            "</context>\n\n"
        )


    def _ensure_tool_message(self, agent_messages: list[AnyMessage]) -> None:
        """
        Make sure tool messages match tool calls in terms of ID, quantity, and order.

        For every ApixAiMessage containing tool calls:

        1. Tool messages immediately follow the corresponding AI message.
        2. Each tool call has exactly one corresponding tool message.
        3. Tool messages follow the order defined by tool_calls.
        4. Existing tool messages are matched using tool_call_id.
        5. Missing tool messages are replaced with placeholder messages.
        6. Duplicate and unmatched tool messages in the contiguous tool
           message block are discarded.

        The original list object is preserved.
        """
        if not agent_messages:
            return

        normalized_messages: list[AnyMessage] = []

        cursor = 0
        total_messages = len(agent_messages)

        while cursor < total_messages:
            current_message = agent_messages[cursor]
            normalized_messages.append(current_message)
            cursor += 1

            if not (
                isinstance(current_message, ApixAiMessage)
                and current_message.tool_calls
            ):
                continue

            # Match only the contiguous ToolMessage block immediately following the current AI message.
            # setdefault keeps the first message when duplicate IDs occur.
            existing_by_call_id: dict[str, ApixToolMessage] = {}

            while (
                cursor < total_messages
                and isinstance(agent_messages[cursor], ApixToolMessage)
            ):
                tool_message = agent_messages[cursor]

                existing_by_call_id.setdefault(
                    tool_message.tool_call_id,
                    tool_message,
                )

                cursor += 1

            seen_call_ids: set[str] = set()

            for tool_index, tool_call in enumerate(
                current_message.tool_calls
            ):
                try:
                    tool_call_id = tool_call["call_id"]
                    tool_name = tool_call["tool_name"]
                except (KeyError, TypeError) as exc:
                    raise ValueError(
                        "Invalid tool call structure: "
                        f"message_index={cursor}, "
                        f"tool_call_index={tool_index}, "
                        f"tool_call={tool_call!r}"
                    ) from exc

                if not tool_call_id:
                    raise ValueError(
                        "Tool call must contain a non-empty call_id: "
                        f"tool_call_index={tool_index}"
                    )

                # A repeated call_id makes one-to-one matching ambiguous.
                if tool_call_id in seen_call_ids:
                    raise ValueError(
                        "Duplicate tool call ID found: "
                        f"tool_call_id={tool_call_id!r}, "
                        f"tool_call_index={tool_index}"
                    )

                seen_call_ids.add(tool_call_id)

                tool_message = existing_by_call_id.get(tool_call_id)

                if tool_message is None:
                    tool_message = ApixToolMessage(
                        content=self._MISSING_TOOL_OUTPUT,
                        name=tool_name,
                        tool_call_id=tool_call_id,
                    )

                normalized_messages.append(tool_message)

        # Preserve the identity of the input list.
        agent_messages[:] = normalized_messages


    def convert_to_apix_messages(
        self,
        dict_messages: list[dict],
        *,
        strict: bool = True
    ) -> Tuple[list[AnyMessage], list[Todo]]:
        """
        Create apix messages list (dict list -> apix message objects list).

        This method is a pure converter:
        - Only transforms dict messages into apix messages.

        Args:
            dict_messages: Message dict list with format:

                ```python
                {
                    "message_uid": str,
                    "generation_id": str, # uuid4, tips: messages generated within the same graph loop share the same generation id.
                    "role": str,
                    "name": str | None,
                    "content": str | list,
                    "node_id": str
                    "parent_id": str,
                    "metadata": dict,
                    "extensions": dict,
                }
                ```

        Returns:
            tuple: A tuple containing two lists:
                - The first element is a list of :class:`ApixMessageBase` objects.
                - The second element is a list of the latest :class:`Todo` items.
        """
        logger.trace()
        logger.info(f"Get dict messages: {len(dict_messages)}.")

        messages = []
        todo: list[Todo] = None

        index = 0
        messages_len = len(dict_messages)
        for msg_dict in dict_messages:
            index = index + 1
            role = msg_dict.get("role")
            content = str(msg_dict.get("content", "") or "")
            metadata = self._decode_json_object(msg_dict.get("metadata"))
            extensions = self._decode_json_object(msg_dict.get("extensions"))
            name = msg_dict.get("name")
            message_uid = msg_dict.get("message_uid")
            message_kwargs = {
                "metadata": metadata,
                "extensions": extensions,
            }
            if message_uid:
                message_kwargs["message_uid"] = message_uid

            if role == "user":
                name = name or "user"
                should_inject_context = bool(todo) and index == messages_len
                content = self._build_user_context(
                    extensions,
                    todo=(todo if should_inject_context else None),
                ) + (content or "")

                if not content:
                    continue

                msg = ApixUserMessage(
                    **message_kwargs,
                    content=content,
                    name=name,
                )
                messages.append(msg)

            elif role == "ai":
                name = name or "assistant"
                suffix = "<conversation_abort>"
                reasoning = str(extensions.get("reasoning", "") or "")
                if content.endswith(suffix):
                    content = content[:-len(suffix)]
                if reasoning.endswith(suffix):
                    reasoning = reasoning[:-len(suffix)]
                    extensions["reasoning"] = reasoning
                tool_calls = extensions.get("tool_calls")
                if not content and not reasoning and not tool_calls:
                    continue  # Skip empty AI message

                msg = ApixAiMessage(
                    **message_kwargs,
                    content=content,
                    name=name,
                )

                messages.append(msg)

            elif role == "system":
                if not content:
                    continue

                msg = ApixSystemMessage(
                    **message_kwargs,
                    content=content,
                    name=name or "system",
                )
                messages.append(msg)

            elif role == "tool":
                if not content:
                    continue

                msg = ApixToolMessage(
                    **message_kwargs,
                    content=content,
                    name=name,
                    tool_call_id=extensions.get("tool_call_id"),
                )
                messages.append(msg)

            elif role == "info":
                if name == "todo":
                    todo_list = extensions.get("todo_list") or []
                    todo = (
                        todo_list
                        if todo_list
                        and todo_list[-1].get("status") != "completed"
                        else None
                    )

            else:
                logger.warning(f"Unknown role or empty content ignored: {role}")

        if strict: self._ensure_tool_message(messages)
        return messages, todo
    
    
    def convert_to_dict_message(
        self,
        message: AnyMessage,
        generation_id: str,
        parent_id: str = '-',
        *,
        filter: bool = False,
    ) -> dict:
        """
        Convert an :class:`ApixAiMessage` or :class:`ApixToolMessage` into a dictionary representation.

        Args:
            message: An instance of `ApixMessageBase` to be converted.
            generation_id: The unique identifier for the current generation loop.
            parent_id: The node ID of the parent message. Defaults to '-'.
            filter: If True, returns a simplified dictionary containing only essential keys

        Returns:
            A dictionary representing the message. The full structure (when `filter=False`) is as follows:

            ```python
            {
                "generation_id": str,   # UUID4; shared by all messages in the same graph loop
                "role": str,
                "content": str | list,
                "message_uid": str,
                "node_id": str,
                "parent_id": str,
                "metadata": dict,
                "extensions": dict,
            }
            ```
        
        Raises:
            TypeError: If message is not an ApixAiMessage or ApixToolMessage.
            
            When ``filter=True``, the returned dict contains ``role``,
            ``content`` and optional ``extensions``.
        """
        logger.trace()

        if not isinstance(message, (ApixAiMessage, ApixToolMessage)):
            raise TypeError(
                "message must be an ApixAiMessage or ApixToolMessage, "
                f"got {type(message).__name__}."
            )

        metadata: dict[str, Any] = copy.deepcopy(message.metadata or {})
        extensions: dict[str, Any] = copy.deepcopy(message.extensions or {})
        content = str(message.content or "")

        if isinstance(message, ApixAiMessage):
            role = "ai"
        else:
            role = "tool"

        if filter:
            result = {
                "role": role,
                "content": content,
            }
            if extensions:
                result["extensions"] = extensions
            return result

        result = {
            "message_uid": message.message_uid,
            "generation_id": generation_id,
            "role": role,
            "name": message.name,
            "content": content,
            "node_id": convert_generation_id_to_message_node_id(
                generation_id,
                role,
            ),
            "parent_id": parent_id,
            "metadata": metadata,
            "extensions": extensions,
        }

        return result

    @staticmethod
    def _decode_json_object(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value or not isinstance(value, str):
            return {}
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    

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

        if min_keep < 0:
            raise ValueError("min_keep must be greater than or equal to zero")

        n = len(input_messages)

        # Tail protected region start index
        protected_start = max(0, n - min_keep)

        # Step1: find last write_todos
        last_todo_idx = -1

        if split_by_todos:
            for i, msg in enumerate(input_messages):
                # Only check ApixAiMessage with tool_calls
                if isinstance(msg, ApixAiMessage):
                    if any(
                        call.get("tool_name") == "write_todos"
                        for call in msg.tool_calls
                    ):
                        last_todo_idx = i
                elif isinstance(msg, ApixAiMessageChunk):
                    if any(
                        delta.tool_name_delta == "write_todos"
                        for delta in msg.tool_call_deltas
                    ):
                        last_todo_idx = i

        # Step2: process messages
        messages_after_drop = []

        for i, msg in enumerate(input_messages):
            # Keep tail untouched (highest priority)
            if i >= protected_start:
                messages_after_drop.append(msg)
                continue

            # Case1: no split or no write_todos found
            if not split_by_todos or last_todo_idx == -1:
                if isinstance(msg, ApixToolMessage):
                    # mark outdated
                    new_msg = copy.copy(msg)
                    new_msg.content = "[Tool Result Outdated]"
                    messages_after_drop.append(new_msg)
                else:
                    messages_after_drop.append(msg)
                continue

            # Case2: split_by_todos=True and found last write_todos
            if isinstance(msg, ApixToolMessage) and i < last_todo_idx:
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
    ) -> Tuple[list[AnyMessage], list[AnyMessage]]:
        """
        Split messages into:
            - messages to summarize
            - recent messages to keep

        The split point will be adjusted to avoid breaking an
        ApixAiMessage(tool_calls) <-> ApixToolMessage chain.

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

        while split_idx > 0 and isinstance(input_messages[split_idx], ApixToolMessage):
            # Find the full tool block that contains split_idx
            tool_start = split_idx
            while tool_start > 0 and isinstance(input_messages[tool_start - 1], ApixToolMessage):
                tool_start -= 1

            tool_end = split_idx
            while tool_end + 1 < len(input_messages) and isinstance(input_messages[tool_end + 1], ApixToolMessage):
                tool_end += 1

            prev_idx = tool_start - 1

            if (
                prev_idx >= 0
                and isinstance(input_messages[prev_idx], ApixAiMessage)
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
        - ApixUserMessage
        - ApixAiMessage(content only)

        ApixToolMessage and ApixAiMessage.tool_calls are dropped.
        ApixSystemMessage will return by a independent message list.

        Return:
            list[AnyMessage]: System message list.
            list[AnyMessage]: AI and human messages after filtered.
            str: message's id
        """
        logger.trace()
        logger.info(f"Client messages count: {len(input_messages)}")

        messages = []
        system_msgs = []
        index = ""

        for input_msg in input_messages:
            if isinstance(input_msg, ApixUserMessage):
                content = input_msg.content or ""
                name = input_msg.name
                messages.append(ApixUserMessage(content=content, name=name))

            elif isinstance(input_msg, ApixAiMessage):
                parts = [
                    part
                    for part in (
                        input_msg.reasoning,
                        input_msg.content,
                    )
                    if isinstance(part, str) and part
                ]
                content = "\n\n".join(parts)
                name = input_msg.name
                index = input_msg.message_uid
                if content:
                    messages.append(ApixAiMessage(content=content, name=name))

            elif isinstance(input_msg, ApixAiMessageChunk):
                content = "\n\n".join(
                    part
                    for part in (
                        input_msg.reasoning_delta,
                        input_msg.content_delta,
                    )
                    if part
                )
                name = input_msg.name
                index = input_msg.message_uid
                if content:
                    messages.append(ApixAiMessage(content=content, name=name))

            elif isinstance(input_msg, ApixSystemMessage):
                system_msgs.append(copy.copy(input_msg))

        logger.info(f"The latest message id is {index}")
        return system_msgs, messages, index



ai_context_adapter = AIContextAdapter()
