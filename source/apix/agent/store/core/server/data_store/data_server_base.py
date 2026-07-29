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
        pass

    @abstractmethod
    async def verify_user(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def ensure_user_exists(self, payload: dict, exist: bool = True) -> dict:
        pass

    # --------------------------------------------------
    # Action of Memo Mysql (Dialog Memory)
    # --------------------------------------------------

    @abstractmethod
    async def fetch_conversation_list(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def get_conversation_meta_by_id(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def create_conversation(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def update_conversation(self, payload: dict) -> dict:
        pass

    # --------------------------------------------------
    # Messages
    # --------------------------------------------------

    @abstractmethod
    async def append_message(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def delete_messages(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def fetch_messages_after_cursor(self, payload: dict) -> dict:
        pass
      
    @abstractmethod  
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        pass
        
    # --------------------------------------------------
    # Skills (meta only)
    # --------------------------------------------------

    async def insert_skill_info(self, payload: dict) -> dict:
        pass

    async def update_skill_status(self, payload: dict) -> dict:
        pass
        
    async def fetch_available_skills(self, payload: dict) -> dict:
        pass

    async def fetch_target_skill(self, payload: dict) -> dict:
        pass
        
    # --------------------------------------------------
    # Short-term Memory 
    # --------------------------------------------------

    @abstractmethod
    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def insert_shortterm_memory(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def delete_shortterm_memory(self, payload: dict) -> dict:
        pass

    # --------------------------------------------------
    # Long-term Memory
    # --------------------------------------------------

    @abstractmethod
    async def fetch_longterm_memory(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def insert_longterm_memory(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def update_longterm_memory(self, payload: dict) -> dict:
        pass
        
    # --------------------------------------------------
    # Custom Provider 
    # --------------------------------------------------

    @abstractmethod
    async def create_llm_provider(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def get_llm_providers(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def get_llm_provider_by_id(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def update_llm_provider(self, payload: dict) -> dict:
        pass
        
    # --------------------------------------------------
    # MCP Server
    # --------------------------------------------------

    @abstractmethod
    async def create_mcp_server(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def get_mcp_servers(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def update_mcp_server(self, payload: dict) -> dict:
        pass
        
    # --------------------------------------------------
    # Cron task
    # --------------------------------------------------

    @abstractmethod
    async def create_cron_task(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def get_all_enabled_cron_tasks(self, payload: dict) -> dict:
        pass

    @abstractmethod
    async def get_cron_tasks(self, payload: dict) -> dict:
        pass
        
    @abstractmethod
    async def get_cron_task_by_id(self, payload: dict) -> dict:
        pass
        
    @abstractmethod
    async def update_cron_task(self, payload: dict) -> dict:
        pass
