"""Profile-driven, client-managed model inference."""

from apix.agent.core.bot.anthropic_bot import AnthropicBot
from apix.agent.core.bot.base import (
    ApiStyle,
    FieldPath,
    ProviderResponseError,
    ReasoningEffort,
    StreamDeltaMode,
)
from apix.agent.core.bot.base_bot import BaseOpenAIBot
from apix.agent.core.bot.bot import BaseBot, Bot
from apix.agent.core.bot.custom_bot import CustomBot
from apix.agent.core.bot.deepseek_bot import DeepSeekBot
from apix.agent.core.bot.gemini_bot import GeminiBot
from apix.agent.core.bot.mimo_bot import XiaomiMIMOBot
from apix.agent.core.bot.minimax_bot import MiniMaxBot
from apix.agent.core.bot.moonshot_bot import MoonshotBot
from apix.agent.core.bot.ollama_bot import OllamaBot
from apix.agent.core.bot.openai_bot import OpenAIBot
from apix.agent.core.bot.openrouter_bot import OpenRouterBot
from apix.agent.core.bot.profile import (
    ANTHROPIC_SCHEMA,
    GEMINI_SCHEMA,
    OPENAI_CHAT_SCHEMA,
    OPENAI_RESPONSES_SCHEMA,
    CustomProfile,
    InvocationPolicy,
    MessageProfile,
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ResponseField,
    ResponseLayout,
    ResponseSchema,
    StreamField,
    ToolProfile,
)
from apix.agent.core.bot.profile.registry import (
    MODELS,
    PROVIDERS,
    REGISTRY,
    ProfileRegistry,
    resolve_model,
    resolve_provider,
)
from apix.agent.core.bot.qwen_bot import QwenBot
from apix.agent.core.bot.siliconflow_bot import SiliconFlowBot
from apix.agent.core.bot.zai_bot import ZAIBot
from apix.agent.core.utils.message import ApixAiMessage as Response
from apix.agent.core.utils.message import ApixAiMessageChunk as StreamEvent


def __getattr__(name):
    if name == "get_custom_provider_meta":
        from apix.agent.store.utils.llm_provider_helper import get_custom_provider_meta

        return get_custom_provider_meta
    raise AttributeError(name)


__all__ = [
    "ANTHROPIC_SCHEMA",
    "GEMINI_SCHEMA",
    "MODELS",
    "OPENAI_CHAT_SCHEMA",
    "OPENAI_RESPONSES_SCHEMA",
    "PROVIDERS",
    "REGISTRY",
    "AnthropicBot",
    "ApiStyle",
    "BaseBot",
    "BaseOpenAIBot",
    "Bot",
    "CustomBot",
    "CustomProfile",
    "DeepSeekBot",
    "FieldPath",
    "GeminiBot",
    "InvocationPolicy",
    "MessageProfile",
    "MiniMaxBot",
    "ModelProfile",
    "MoonshotBot",
    "OllamaBot",
    "OpenAIBot",
    "OpenRouterBot",
    "ProfileRegistry",
    "ProviderProfile",
    "ProviderResponseError",
    "QwenBot",
    "ReasoningEffort",
    "ReasoningProfile",
    "RequestField",
    "Response",
    "ResponseField",
    "ResponseLayout",
    "ResponseSchema",
    "SiliconFlowBot",
    "StreamDeltaMode",
    "StreamEvent",
    "StreamField",
    "ToolProfile",
    "XiaomiMIMOBot",
    "ZAIBot",
    "get_custom_provider_meta",
    "resolve_model",
    "resolve_provider",
]
