import copy
from typing import List, Tuple
import json
import os
from typing import Any
from xml.sax.saxutils import escape

from apix.agent.sdk.utils.message import ApixMessageBase, ApixSystemMessage, ApixAiMessageChunk, ApixUserMessage, ApixToolMessage, ApixAiMessage, AnyMessage
from apix.agent.sdk.graph.state import MainAgentState, Memory, Skill, Todo, Memory
from apix.common.utils.logger import logger


class AIContextAdapter:
    """Context adapter for agent sdk.
    """

    _MISSING_TOOL_OUTPUT = (
        "[The outputs of this tool have been lost, or the tool's execution was interrupted by the user.]"
    )

    def build_runtime_context(
            self, 
            agent_messages: list[AnyMessage], 
            *,
            todo: list[Todo] | None = None,
            skill: list[Skill] | None = None,
            memory: list[Memory] | None = None,
            workspace: str | None = None
        ) -> list[AnyMessage]:
        """Build a frequently updated prompt and inject it into the last message object.
        The last object in `agent_messages` should be a :class:`ApixUserMessage`.

        Args:
            agent_messages: A list of :class:`ApixMessageBase` instances.
            todo: Optional, the current todo list.
            skill: Optional, the current skill list.
            memory: Optional, the current memory list.
            workspace: Optional, the current workspace directory in the sandbox.

        Returns:
            list[AnyMessage]: The message list after injection.

        Raises:
            ValueError: If the last message in the list is not a :class:`ApixUserMessage`.
        """
        pass
    

    def _build_user_context(self, extra: dict[str, Any], todo: list[Todo] = None) -> str:
        context_parts: list[str] = []

        referenced_message = extra.get("referenced_message") or {}
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

        active_file = extra.get("active_file") or ""
        if active_file:
            context_parts.append(
                f"<active_file>{escape(str(active_file))}</active_file>"
            )

        uploaded_files = extra.get("uploaded_files") or []
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

        task = extra.get("task") or {}
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
                    "generation_id": str, # uuid4, tips: messages generated within the same graph loop share the same generation id.
                    "role": str,
                    "content": str | list,
                    "created_at": int
                    "node_id": str
                    "parent_id": str,
                    "think": str, # optional
                    "extra": dict, # optional, contains key: `active_file: str` `referenced_message: dict` `system_instruction: list`
                    "info": dict, # optional
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
        messages_len = len(messages)
        for msg_dict in dict_messages:
            index = index + 1
            role = msg_dict.get("role")
            content = str(msg_dict.get("content", "") or "")
            think = str(msg_dict.get("think", "") or "")
            extra = msg_dict.get("extra", {})
            if extra and not isinstance(extra, dict):
                extra = json.loads(extra)
            info = msg_dict.get("info", {})
            if info and not isinstance(info, dict):
                info = json.loads(info)
            created_at = msg_dict.get("created_at", "")
            name = info.get("name")
            id = info.get("id")

            if role == "user":
                name = name or "user"
                should_inject_todo = bool(todo) and index == messages_len
                content = self._build_user_context(extra, todo=(todo if should_inject_todo else None)) + (content or "")

                if not content:
                    continue

                msg = ApixUserMessage(
                    id=id, 
                    content=content, 
                    name=name, 
                    timestamp=created_at, 
                    info=info, 
                    extra=extra
                )
                messages.append(msg)

            elif role == "ai":
                name = name or "assistant"
                suffix = "<conversation_abort>"
                if content.endswith(suffix):
                    content = content[:-len(suffix)]
                if think.endswith(suffix):
                    think = think[:-len(suffix)]
                tool_calls = extra.get("tool_calls")
                if not content and not think and not tool_calls:
                    continue  # Skip empty AI message

                msg = ApixAiMessage(
                    id=id,
                    content=content,
                    name=name,
                    timestamp=created_at, 
                    info=info, 
                    extra=extra,
                    tool_calls=tool_calls,
                    reasoning=think
                )

                messages.append(msg)

            elif role == "system":
                if not content:
                    continue

                msg = ApixSystemMessage(
                    id=id,
                    content=content,
                    name='system',
                    timestamp=created_at, 
                    info=info, 
                    extra=extra,
                )
                messages.append(msg)

            elif role == "tool":
                if not content:
                    continue

                msg = ApixToolMessage(
                    id=id,
                    content=content,
                    name=name,
                    tool_call_id=info.get("tool_call_id"),
                    timestamp=created_at,
                    info=info,
                    extra=extra,
                )
                messages.append(msg)

            elif role == "info":
                if name == "todo":
                    todo = extra.get("todo_list") if extra.get("todo_list")[-1]["status"] != "completed" else None

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
                "created_at": int,
                "node_id": str,
                "parent_id": str,
                "think": str,           # optional
                "extra": dict,          # optional
                "info": dict            # optional
            }
            ```
        
        Raises:
            TypeError: If message is not an ApixAiMessage or ApixToolMessage.
            
        When `filter=True`, the returned dict will only contains `role`, `content` and optional `think` and `extra`.
        """
        logger.trace()

        if not isinstance(message, (ApixAiMessage, ApixToolMessage)):
            raise TypeError(
                "message must be an ApixAiMessage or ApixToolMessage, "
                f"got {type(message).__name__}."
            )

        info: dict[str, Any] = copy.deepcopy(message.info or {})
        extra: dict[str, Any] = copy.deepcopy(message.extra or {})
        content = str(message.content or "")
        think = ""

        if message.id is not None:
            info["id"] = message.id
        if message.name is not None:
            info["name"] = message.name

        if isinstance(message, ApixAiMessage):
            role = "ai"
            think = str(message.reasoning or "")
            if message.tool_calls:
                extra["tool_calls"] = copy.deepcopy(message.tool_calls)
            else:
                extra.pop("tool_calls", None)

        else:
            role = "tool"
            if message.tool_call_id is not None:
                info["tool_call_id"] = message.tool_call_id
            else:
                info.pop("tool_call_id", None)

        if filter:
            result = {
                "role": role,
                "content": content,
            }
            if think:
                result["think"] = think
            if extra:
                result["extra"] = extra
            return result

        result = {
            "generation_id": generation_id,
            "role": role,
            "content": content,
            "created_at": message.timestamp,
            "node_id": message.id,
            "parent_id": parent_id,
        }

        if think:
            result["think"] = think
        if extra:
            result["extra"] = extra
        if info:
            result["info"] = info

        return result
    

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
                # Only check ApixAiMessage with tool_calls
                if isinstance(msg, (ApixAiMessage, ApixAiMessageChunk)):
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
    ) -> Tuple[list[AnyMessage], list[AnyMessage], list[ApixSystemMessage]]:
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
            content = input_msg.content
            if content is None:
                content = ""

            if isinstance(input_msg, ApixUserMessage):
                name = input_msg.name
                messages.append(ApixUserMessage(content=content, name=name))

            elif isinstance(input_msg, ApixAiMessage) or isinstance(input_msg, ApixAiMessageChunk):
                think_content = (input_msg.additional_kwargs or {}).get("reasoning_content", "")
                content = think_content + '\n\n' + content
                msg = ApixAiMessage(content=content)
                index = input_msg.id
                if not content: continue
                messages.append(msg)

            elif isinstance(input_msg, ApixSystemMessage):
                system_msgs.append(copy.copy(input_msg))

        logger.info(f"The latest message id is {index}")
        return system_msgs, messages, index
        
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
        sandbox = state.get("sandbox", "")
        config = state.get("config", {})
        workspace = config.get("workspace", "")

        if not workspace:
            return "## No workspace directory has been specified by the user.\n\n"

        if not os.path.exists(workspace):
            raise FileNotFoundError(f"Workspace directory does not exist: {workspace}")

        if not sandbox:
            return "## Sandbox configuration failed.\n\n"

        return f"""## Sandbox Environment

An Ubuntu sandbox is available and shared with the user.

Workspace mapping:
{workspace} → /workspace

Rules:
- Use `/workspace` as the workspace root inside the sandbox.
- Prefer relative paths in project code file whenever possible.
- Never expose `/workspace` in user-facing responses.
- When showing file paths to the user, always use `{workspace}`.

Examples:

Sandbox usage:
- Read file: /workspace/data/input.csv
- Write file: /workspace/output/report.pdf
- Preferred in project code: open("data/input.csv")

User-facing output:
- Show image in Markdown: ![Image]({workspace}/images/result.png)
- Report output file: File saved to: {workspace}/report.pdf
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
        memorandum_list: List[Memory] = state.get("memorandum", [])

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
        blocks.append(ApixSystemMessage(content=(state.get("rule_prompt", "") + "\n\n" + self.create_workflow_prompt(state, agent_role))))
        # 2. Longterm memory
        if state.get("longterm_memory"):
            blocks.append(ApixSystemMessage(
                content="# [LONGTERM MEMORY]\n" + (state["longterm_memory"] or "None")
            ))
        # 3. Shortterm summary
        if state.get("shortterm_memory"):
            blocks.append(ApixSystemMessage(
                content="# [RECENT SUMMARY / SHORT-TERM MEMORY]\n" + (state["shortterm_memory"] or "None")
            ))
        # 4. Runtime
        if state.get("runtime_prompt"):
            blocks.append(ApixSystemMessage(
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
        if not higher_role_prompt_permission: return [ApixUserMessage(content=structured)]
        else: return [ApixSystemMessage(content=structured)]



ai_context_adapter = AIContextAdapter()
