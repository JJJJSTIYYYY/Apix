from abc import ABC, abstractmethod

from apix.agent.store.utils.id_generator import idgen


class DataServerBase(ABC):

    def __init__(self):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    def _conversation_id_generator(self) -> str:
        """
        Generate a unique conversation ID using Yuki IdGenerator.
        """
        uid = idgen.next_id()
        return str(uid)
            
    # --------------------------------------------------
    # Action of Memo Mysql (Dialog Memory)
    # --------------------------------------------------

    @abstractmethod
    async def create_a_user(self, payload: dict) -> dict:
        """
        Ensure user account exists.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "user_uid": str, # user_uid
                "username": str,
                "password": str, # encrypted
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    @abstractmethod
    async def verify_user(self, payload: dict) -> dict:
        """
        Ensure user account exists.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "username": str,
                "password": str, # encrypted
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    @abstractmethod
    async def ensure_user_exists(self, payload: dict, exist: bool = True) -> dict:
        """
        Ensure user account exists.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
            }
            exist: ensure exist if ture, else ensure not exist.

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    # --------------------------------------------------
    # Action of Memo Mysql (Dialog Memory)
    # --------------------------------------------------

    @abstractmethod
    async def fetch_conversation_list(self, payload: dict) -> dict:
        """
        Get conversation history list for a user.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [
                    {
                        "conversation_uid": str,
                        "session_id": str,
                        "title": str,
                        "work_space": str,
                        "last_active_at": str,
                        "created_at": str,
                        "latest_cursor": int,
                        "is_pinned": bool,
                        "has_new_message": bool
                    },
                    ...
                ],
            }
        """
        pass

    @abstractmethod
    async def get_conversation_meta_by_id(self, payload: dict) -> dict:
        """
        Get a conversation metadata.

        Args:
            payload: Dict, the format is {
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [
                    {
                        "conversation_uid": str,
                        "session_id": str,
                        "title": str,
                        "work_space": str,
                        "last_active_at": str,
                        "created_at": str,
                        "latest_cursor": int,
                        "is_pinned": bool,
                        "has_new_message": bool
                    },
                ],
            }
        """
        pass

    @abstractmethod
    async def create_conversation(self, payload: dict) -> dict:
        """
        Create a new conversation record.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "platform": str,
                "title": "conversation title",
                "workspace": "Agent work dir",
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or {"conversation_uid": conversation_uid},
            }
        """
        pass

    @abstractmethod
    async def update_conversation(self, payload: dict) -> dict:
        """
        Update a conversation record.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "title": "Conversation title",
                "workspace": "Agent work dir",
                "is_pinned": bool,
                "is_deleted": bool,
                "has_new_message": bool
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    # --------------------------------------------------
    # Messages
    # --------------------------------------------------

    @abstractmethod
    async def append_message(self, payload: dict) -> dict:
        """
        Persist a message.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "message": {
                    "message_uid": unique message id,
                    "generation_id": str,
                    "role": 'user', 'ai', 'system', 'tool', 'info'
                    "name": "assistant / user / tool name",
                    "content": "message content",
                    "metadata": {...},
                    "extensions": {...},
                    "node_id": str,
                    "parent_id": str,
                }
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or {
                    "msg_cursor": int,
                    "timestamp": int,
                },
            }
        """
        pass

    @abstractmethod
    async def delete_messages(self, payload: dict) -> dict:
        """
        Persist a peice of message.
        If len of messages list in payload is over one piece, only append the last one.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "messages": [ 
                    str, 
                    ...
                ] # list of message node_id
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list[dict],
            }
        """
        pass

    @abstractmethod
    async def fetch_messages_after_cursor(self, payload: dict) -> dict:
        """
        Get a batch of messages after cursor (include this cursor).

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "cursor": int, # fetch messages with msg_cursor >= after_cursor
                "limit": int, # max number of messages to fetch
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [
                    {
                        "message_uid": str,
                        "generation_id": str,
                        "role": str,
                        "name": str,
                        "content": str,
                        "node_id": str,
                        "parent_id": str,
                        "metadata": dict,
                        "extensions": dict,
                        "msg_cursor": int,
                        "timestamp": datetime,
                        "is_deleted": bool
                    },
                    ...
                ],
                "next_cursor": int.
            }
        """
        pass
      
    @abstractmethod  
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        """
        Search messages in all conversations.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
                "keyword": str
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [
                    {
                        "conversation_uid": str,
                        "generation_id": str,
                        "role": str, # message role
                        "content": str, # message content
                        "title": str, # conversation title
                        "last_active_at": str
                    },
                    ...
                ],
            }
        """
        pass
        
    # --------------------------------------------------
    # Skills (meta only)
    # --------------------------------------------------

    async def insert_skill_info(self, payload: dict) -> dict:
        """
        Insert uploaded skill metadata into MySQL.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "skills": [
                    {
                        "skill_id": str,
                        "skill_name": str,
                        "skill_description": str,
                        "skill_version": str,
                        "package_path": str,
                        "package_size": int,
                        "package_sha256": str,
                    },
                    ...
                ]
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "success" or "fail: {e}",
            }
        """
        pass

    async def update_skill_status(self, payload: dict) -> dict:
        """
        Update skill status (activate / deactivate / delete).

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "skill_id": str,
                "is_active": bool | None,
                "deleted": bool | None,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass
        
    async def fetch_available_skills(self, payload: dict) -> dict:
        """
        Fetch available skills for user.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "limit": int, // Optional, default 5.
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": [
                    {
                        "skill_id": str,
                        "skill_name": str,
                        "skill_description": str,
                        "skill_version": str,
                        "package_path": str,
                        "package_size": int,
                        "is_active": bool,
                        "upload_at": str,
                    },
                    ...
                ]
            }
        """
        pass

    async def fetch_target_skill(self, payload: dict) -> dict:
        """
        Fetch target skill for user.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "skill_id": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": [
                    {
                        "skill_id": str,
                        "skill_name": str,
                        "skill_description": str,
                        "skill_version": str,
                        "package_path": str,
                        "package_size": int,
                        "is_active": bool,
                        "upload_at": str,
                    }
                ]
            }
        """
        pass
        
    # --------------------------------------------------
    # Short-term Memory 
    # --------------------------------------------------

    @abstractmethod
    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [
                    {
                        "memory_id": str,
                        "content": str,
                        "created_timestamp": int,
                    },
                ],
            }
        """
        pass

    @abstractmethod
    async def insert_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories.

        Args:
            payload: Dict, the format is {
                "memory_id": str, # Related message_uid
                "user_uid": user id,,
                "conversation_uid": conversation id,
                "content": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    @abstractmethod
    async def delete_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories.

        Args:
            payload: Dict, the format is {
                "memory_ids": list[str], # Related message_uid values
                "user_uid": user id,,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    # --------------------------------------------------
    # Long-term Memory
    # --------------------------------------------------

    @abstractmethod
    async def fetch_longterm_memory(self, payload: dict) -> dict:
        """
        Fetch all active long-term memories owned by a user.
        
        Args:
            payload: Dict, the format is {
                "user_uid": str, # user id
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [
                    {
                        "memory_id": str,
                        "title": str,
                        "date": str,
                        "content": str,
                        "source": str
                    },
                    ...
                ]
            }
        """
        pass

    @abstractmethod
    async def insert_longterm_memory(self, payload: dict) -> dict:
        """
        Insert one long-term memory.

        Args:
            payload: Dict, the format is {
                "memory_id": str, # memory's unique id (uuid4)
                "user_uid": str, # to indicate which user the data is from
                "title": str, # memory's title, not null
                "date": str, # memory's date, not null
                "content": str, # memory's content, not null
                "source": str, # memory's source, not null
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or dict {"memory_id": str},
            }
        """
        pass

    @abstractmethod
    async def update_longterm_memory(self, payload: dict) -> dict:
        """
        Partially update or soft-delete one long-term memory.

        Args:
            payload: Dict, the format is {
                "memory_id": str, # memory's unique id (uuid4)
                "user_uid": str, # to indicate which user the data is from
                "title": str, # Optional, memory's title
                "date": str, # Optional, memory's date
                "content": str, # Optional, memory's content
                "source": str, # Optional, memory's source
                "is_deleted": bool, # Optional, delete if true
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass
        
    # --------------------------------------------------
    # Custom Provider 
    # --------------------------------------------------

    @abstractmethod
    async def create_llm_provider(self, payload: dict) -> dict:
        """
        Insert a llm provider meta in database.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
                "user_uid": str, # to indicate which user the data is from
                "provider_name": str, # provider's name, not null
                "type": str, # provider's protocol, default openai
                "endpoint": str, # provider's endpoint, not null
                "model_list": str, # provider's model list, not null
                "description": str, # description for provider, default null
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or dict {"provider_id": str},
            }
        """
        pass

    @abstractmethod
    async def get_llm_providers(self, payload: dict) -> dict:
        """
        Get all llm provider meta in database.

        Args:
            payload: Dict, the format is {
                "user_uid": str, # to indicate which user the request from
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list [
                    {
                        "provider_id": str,
                        "provider_name": str,
                        "type": str,
                        "endpoint": str,
                        "model_list": list,
                        "description": str,
                        "created_at": str
                    },
                    ...
                ],
            }
        """
        pass

    @abstractmethod
    async def get_llm_provider_by_id(self, payload: dict) -> dict:
        """
        Get a llm provider meta in database.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list [
                    {
                        "provider_id": str,
                        "provider_name": str,
                        "type": str,
                        "endpoint": str,
                        "model_list": list,
                        "description": str,
                        "created_at": str
                    }
                ],
            }
        """
        pass

    @abstractmethod
    async def update_llm_provider(self, payload: dict) -> dict:
        """
        Update a llm provider meta in database, include is_deleted status.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
                "user_uid": str, # to indicate which user the data is from
                "provider_name": str, # Optional, provider's name
                "type": str, # Optional, provider's protocol
                "endpoint": str, # Optional, provider's endpoint
                "model_list": str, # Optional, provider's model list
                "description": str, # Optional, description for provider
                "is_deleted": bool, # Optional, delete if true
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass
        
    # --------------------------------------------------
    # MCP Server
    # --------------------------------------------------

    @abstractmethod
    async def create_mcp_server(self, payload: dict) -> dict:
        """
        Insert a mcp server meta in database.

        Args:
            payload: Dict, the format is {
                "mcp_id": str,
                "user_uid": str,
                "mcp_name": str,
                "transport": str,
                "endpoint": str,
                "config": dict,
                "description": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or {
                    "mcp_id": str
                },
            }
        """
        pass

    @abstractmethod
    async def get_mcp_servers(self, payload: dict) -> dict:
        """
        Get all mcp servers in database.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list [
                    {
                        "mcp_id": str,
                        "mcp_name": str,
                        "transport": str,
                        "endpoint": str,
                        "config": dict,
                        "description": str,
                        "enabled": bool,
                        "tool_count": int,
                        "created_at": str
                    },
                    ...
                ]
            }
        """
        pass

    @abstractmethod
    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        """
        Get enabled mcp servers in database.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list [
                    {
                        "mcp_id": str,
                        "mcp_name": str,
                        "transport": str,
                        "endpoint": str,
                        "config": dict,
                    },
                    ...
                ]
            }
        """
        pass

    @abstractmethod
    async def update_mcp_server(self, payload: dict) -> dict:
        """
        Update a mcp server meta in database.

        Args:
            payload: Dict, the format is {
                "mcp_id": str,
                "user_uid": str,
                "mcp_name": str,
                "transport": str,
                "endpoint": str,
                "config": dict,
                "description": str,
                "enabled": bool,
                "tool_count": int,
                "is_deleted": bool,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "success" or "fail: {e}"
            }
        """
        pass
        
    # --------------------------------------------------
    # Cron task
    # --------------------------------------------------

    @abstractmethod
    async def create_cron_task(self, payload: dict) -> dict:
        """
        Create a cron task in database.

        Args:
            payload: Dict, the format is {
                "task_id": str,
                "user_uid": str,
                "conversation_uid": str,
                "platform": str,
                "task_name": str,
                "prompt": str,
                "execute": str,
                "exec_time": str, # ISO-8601
                "repeat": Literal["once", "day", "week", "month", "year"],
                "extra_config": dict,
                "description": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or {
                    "task_id": str
                }
            }
        """
        pass

    @abstractmethod
    async def get_all_enabled_cron_tasks(self, payload: dict) -> dict:
        """
        Get all cron tasks in database.

        Args:
            payload: Dict, the format is { }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list [
                    { 
                        "task_id": str,
                        "user_uid": str,
                        "conversation_uid": str,
                        "platform": str,
                        "name": str,
                        "prompt": str,
                        "execute": str,
                        "exec_time": str,
                        "repeat": str,
                        "extra_config": dict,
                        "description": str,
                        "created_at": str,
                        "updated_at": str
                    },
                    ...
                ]
            }
        """
        pass

    @abstractmethod
    async def get_cron_tasks(self, payload: dict) -> dict:
        """
        Get all cron tasks in database.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list [
                    { 
                        "task_id": str,
                        "conversation_uid": str,
                        "platform": str,
                        "name": str,
                        "prompt": str,
                        "execute": str,
                        "exec_time": str,
                        "repeat": str,
                        "extra_config": dict,
                        "description": str,
                        "enabled": bool,
                        "created_at": str,
                        "updated_at": str
                    },
                    ...
                ]
            }
        """
        pass
        
    @abstractmethod
    async def get_cron_task_by_id(self, payload: dict) -> dict:
        """
        Get a cron task in database.

        Args:
            payload: Dict, the format is {
                "task_id": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list [
                    { 
                        "task_id": str,
                        "user_uid": str,
                        "conversation_uid": str,
                        "platform": str,
                        "name": str,
                        "prompt": str,
                        "execute": str,
                        "exec_time": str,
                        "repeat": str,
                        "extra_config": dict,
                        "description": str,
                        "enabled": bool,
                        "created_at": str,
                        "updated_at": str
                    },
                ]
            }
        """
        pass
        
    @abstractmethod
    async def update_cron_task(self, payload: dict) -> dict:
        """
        Update a cron task in database.

        Args:
            payload: Dict, the format is {
                "task_id": str,
                "conversation_uid": str,
                "platform": str,
                "task_name": str,
                "prompt": str,
                "execute": str,
                "exec_time": str, # ISO-8601
                "repeat": Literal["once", "day", "week", "month", "year"],
                "extra_config": dict,
                "description": str,
                "is_deleted": bool,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success"
            }
        """
        pass
