from openai import OpenAI

from apix.agent.sdk.utils.funcs import convert_generation_id_to_message_node_id
from apix.agent.sdk.adapter.model.base_model import BaseModel
from apix.config.base_config import PROVIDER_BASE_URL


class DeepSeekModel(BaseModel):
    """DeepSeek adapter.
    """
    provider: str
    default_max_retry: int
    base_url: str
    api_key: str

    def __init__(self, base_url, api_key):
        super().__init__(base_url, api_key)
        self.provider = "deepseek"
        if not base_url:
            self.base_url = PROVIDER_BASE_URL.get("deepseek", "https://api.deepseek.com")
        