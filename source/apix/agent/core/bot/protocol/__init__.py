from apix.agent.core.bot.protocol.anthropic import AnthropicProtocol
from apix.agent.core.bot.protocol.base import BaseProtocol
from apix.agent.core.bot.protocol.gemini import GeminiProtocol
from apix.agent.core.bot.protocol.ollama import OllamaProtocol
from apix.agent.core.bot.protocol.openai import OpenAIProtocol

PROTOCOLS = {
    "openai": OpenAIProtocol,
    "anthropic": AnthropicProtocol,
    "gemini": GeminiProtocol,
    "ollama": OllamaProtocol,
}

__all__ = [
    "PROTOCOLS",
    "AnthropicProtocol",
    "BaseProtocol",
    "GeminiProtocol",
    "OllamaProtocol",
    "OpenAIProtocol",
]
