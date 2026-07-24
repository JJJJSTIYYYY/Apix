from abc import ABC, abstractmethod
from typing import Literal

from apix.agent.sdk.utils.message import ApixAiMessage, ApixAiMessageChunk, MessageContext
from apix.config.base_config import LLM_MAX_RETRY


class BaseModel(ABC):
    """Base class for llm provider.
    """
    provider: str
    default_max_retry: int
    base_url: str
    api_key: str
    chat_api: str
    model_list: str

    def __init__(self, base_url: str, api_key: str):
        self.api_key = api_key
        self.base_url = base_url
        self.default_max_retry = LLM_MAX_RETRY

    def _parse_tool_schema(self, tool_schema: dict):
        return tool_schema
    
    @abstractmethod
    async def invoke(
        self, 
        model_name: str, 
        reasoning: bool = True, 
        reasoning_effort: Literal["low", "medium", "high"] = "high", 
        extra_body: dict = {},
        bind_context: MessageContext = {}
    ) -> ApixAiMessage:
        """Invoke a LLM without streaming.

        Args:
            model_name: The model identifier to use.
            reasoning: Enable reasoning/CoT mode. Default False.
            reasoning_effort: Reasoning depth: "low", "medium", or "high". Only used when reasoning=True. Default "high".
            extra_body: Additional JSON parameters to merge into the request body.
            bind_context: MessageContext for generation/parent node tracking. Pass empty string to omit.

        Returns:
            ApixAiMessage: The complete non-streaming response from the model.
        """
        pass

    @abstractmethod
    async def stream(
        self,
        model_name: str, 
        reasoning: bool = False, 
        reasoning_effort: Literal["low", "medium", "high"] = "high", 
        extra_body: dict = {},
        bind_context: MessageContext = {}
    ) -> ApixAiMessageChunk:
        """Stream responses from a LLM.

        Args:
            model_name: The model identifier to use.
            reasoning: Enable reasoning/chain-of-thought mode. Default False.
            reasoning_effort: Reasoning depth: "low", "medium", or "high". Only used when reasoning=True. Default "high".
            extra_body: Additional JSON parameters to merge into the request body.
            bind_context: MessageContext for generation/parent node tracking. Pass empty string to omit.

        Returns:
            ApixAiMessageChunk: A stream of response chunks from the model.
        """