import hashlib
from pathlib import Path
from uuid import uuid4

from apix.agent.store import query_store
from apix.agent.sdk.utils.message import AnyMessage
from apix.agent.sdk.adapter.context.context_adapter import ai_context_adapter
from apix.agent.sdk.utils.funcs import check_identity, convert_generation_id_to_message_node_id
from apix.agent.sdk.graph.state import MainAgentState, Memory, Todo
from apix.common.type import ApixIdentity
from apix.common.utils.logger import logger
from apix.common.utils.yaml import load_from_yaml


class AIStoreAdapter:
    """Store adapter for agent sdk."""


    async def append_to_store(
        self, 
        message: AnyMessage | dict,
        identity: ApixIdentity,
        generation_id: str,
        parent_id: str = '-',
    ) -> None:
        """
        Append a single message to the store.

        Args:
            message: An instance of :class:`ApixMessageBase` or a dict representing the message.
            identity: An instance of :class:`ApixIdentity` representing the identity context.
            generation_id: The unique identifier for the current generation loop.
            parent_id: The node ID of the parent message. Defaults to '-'.

        Raises:
            IdentityError: If the identity is not provided or is ambiguous.
            RuntimeError: If `generation_id` is not provided.

        Notes:
            When `message` is provided as a dict, it must follow this structure:

            ```python
            {
                "message_uid": str,
                "generation_id": str,   # UUID4; all messages in the same graph loop share this ID
                "role": str,
                "name": str | None,
                "content": str | list,
                "node_id": str,
                "parent_id": str,
                "metadata": dict,
                "extensions": dict,
            }
            ```

        parent_id only be used to call :meth:`AIStoreAdapter.convert_to_dict_message` for ApixMessageBase.
        """
        logger.trace()

        if not message: return
        user_uid, _, conversation_uid, _ = check_identity(identity)

        if conversation_uid.startswith("sub_"): 
            logger.info("Sub-assistant conversation, skip.")
            return

        if not isinstance(message, dict):
            message = ai_context_adapter.convert_to_dict_message(
                message,
                generation_id,
                parent_id,
            )

        payload = {
            "user_uid": user_uid,
            "conversation_uid": conversation_uid,
            "messages": message,
        }

        await query_store(action="append_message", payload=payload)
    
    
    async def append_info_to_store(
        self,
        extensions: dict,
        metadata: dict,
        identity: ApixIdentity,
        generation_id: str,
        parent_id: str = '-',
        name: str | None = None,
    ):
        """
        Append an ``info`` role message containing business extensions.

        Args:
            extensions: Business data such as todo/search results.
            metadata: Usage, provider, duration, and similar metadata.
            identity: An instance of :class:`ApixIdentity` representing the identity context.
            generation_id: The unique identifier for the current generation loop.
            parent_id: The node ID of the parent message. Defaults to '-'.
            name: Information message kind, for example ``todo`` or ``search``.

        Returns:
            None
        """
        logger.trace()
        message = {
            "message_uid": uuid4().hex,
            "generation_id": generation_id,
            "role": "info",
            "name": name,
            "content": "",
            "node_id": convert_generation_id_to_message_node_id(generation_id, 'ai'),
            "parent_id": parent_id,
            "metadata": metadata or {},
            "extensions": extensions or {},
        }
        await self.append_to_store(
            message,
            identity,
            generation_id,
            parent_id,
        )

        
    async def insert_shortterm_memory(self, user_uid: str, conversation_uid: str, memory_id: str, content: str):
        """
        Insert shortterm memory to memory service.

        Args:
            user_uid: "Id to indicate which user the data is from.",
            conversation_uid: history id,
            memory_id: The related message's ``message_uid``.
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

        def load_memories(namespace: str) -> list[Memory]:
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
        



ai_store_adapter = AIStoreAdapter()
