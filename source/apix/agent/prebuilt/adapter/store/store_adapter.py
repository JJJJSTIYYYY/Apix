import hashlib
from pathlib import Path
from uuid import uuid4

from apix.agent.store import query_store
from apix.agent.sdk.utils.message import AnyMessage
from apix.agent.prebuilt.adapter.context.context_adapter import ai_context_adapter
from apix.agent.sdk.utils.funcs import check_identity, convert_generation_id_to_message_node_id
from apix.agent.sdk.utils.context import LongtermMemory, ShorttermMemory, Skill, Todo
from apix.common.type import ApixIdentity
from apix.common.utils.logger import logger
from apix.common.utils.yaml import load_from_yaml


class AIStoreAdapter:
    """Store adapter for agent sdk."""


    async def append_message_to_store(
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
        await self.append_message_to_store(
            message,
            identity,
            generation_id,
            parent_id,
        )

        
    async def append_shortterm_to_store(self, content: str, identity: ApixIdentity, memory_id: str):
        """
        Append a shortterm memory to store.

        Args:
            content: the content of this shortterm memory.
            identity: An instance of :class:`ApixIdentity` representing the identity context.
            memory_id: The related message's ``message_uid``.

        Returns:
            None
        """
        logger.trace()
        content = content.strip()
        if not content: 
            logger.error("Can not append an empty memory to database.")
            return
        user_uid, _, conversation_uid, _ = check_identity(identity)
        
        payload = {
            "memory_id": memory_id,
            "user_uid": user_uid,
            "conversation_uid": conversation_uid,
            "content": content
        }

        await query_store(action="insert_shortterm_memory", payload=payload)
        
        
    async def get_messages_from_store(
        self,
        identity: ApixIdentity,
        current_node_id: str = '-',
        preserved_context_window: int = 999
    ) -> tuple[list[dict], str]:
        """
        Get messages from store.

        Args:
            identity: An instance of :class:`ApixIdentity` representing the identity context.
            current_node_id: The currently visible latest message node id.

        Returns:
            list[dict]: Message dict list returned by memory service.
        """
        logger.trace()

        user_uid, _, conversation_uid, _ = check_identity(identity)
        payload = {
            "user_uid": user_uid,
            "conversation_uid": conversation_uid,
            "current_node_id": current_node_id,
            "cursor": 0,  # reserved
            "limit": preserved_context_window
        }

        result = await query_store(action="get_messages", payload=payload)

        messages = result.get("messages", [])
        chain = result.get("current_chain", [])
        if len(chain) == 0:
            chain = ['-']

        logger.info(f"Fetched {len(messages)} messages. Current message chain: {chain}")

        return messages, chain[-1]
    

    async def get_shortterm_from_store(self, identity: ApixIdentity) -> list[ShorttermMemory]:
        """
        Get shortterm memory from store.

        Args:
            identity: An instance of :class:`ApixIdentity` representing the identity context.

        Returns:
            list[ShorttermMemory]: :class:`ShorttermMemory` dict list.
        """
        logger.trace()

        user_uid, _, conversation_uid, _ = check_identity(identity)
        try:
            payload = {
                "user_uid": user_uid,
                "conversation_uid": conversation_uid,
            }

            result = await query_store(action="fetch_shortterm_memory", payload=payload)
            return result.get("messages", [])
            
        except Exception as e:
            logger.error(f"Load shortterm memory error: {e}, skip.")
            return []
    
    
    async def get_longterm_from_store(self, identity: ApixIdentity, workspace: str | None = None) -> list[LongtermMemory]:
        """
        Get the longterm memory from store.
        A longterm memory should be separated by workspace or conversation.

        Args:
            identity: An instance of :class:`ApixIdentity` representing the identity context.

        Returns: 
            list[LongtermMemory]: :class:`LongtermMemory` dict list.
        """
        logger.trace()

        user_uid, _, conversation_uid, _ = check_identity(identity)
        try:
            payload = {
                "user_uid": user_uid,
                "conversation_uid": conversation_uid,
                "workspace": workspace
            }

            result = await query_store(action="fetch_longterm_memory", payload=payload)
            return result.get("messages", [])
            
        except Exception as e:
            logger.error(f"Load longterm memory error: {e}, skip.")
            return []
    

    async def get_skills_from_store(self, identity: ApixIdentity) -> list[Skill]:
        """
        Get the skills metadata from store.

        Args:
            identity: An instance of :class:`ApixIdentity` representing the identity context.

        Returns: 
            list[Skill]: :class:`Skill` dict list.
        """
        user_uid, _, _, _ = check_identity(identity)
        try:
            payload = {
                "user_uid": user_uid,
                "limit": 999
            }
            result = await query_store(action="fetch_skills", payload=payload)
            skills = result.get("messages", []) or []
            visible_skills = []
            for skill in skills:
                if skill.get("is_active"):
                    visible_skills.append(Skill(
                        skill_id=skill.get("skill_id"),
                        skill_name=skill.get("skill_name"),
                        description=skill.get("skill_description")
                    ))
            return visible_skills
        
        except Exception as e:
            logger.error(f"Load skills error: {e}, skip.")
            return []



ai_store_adapter = AIStoreAdapter()
