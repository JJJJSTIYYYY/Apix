from apix.agent.core.bot.codec.anthropic_messages import AnthropicMessagesCodec
from apix.agent.core.bot.codec.chat_completions import ChatCompletionsCodec
from apix.agent.core.bot.codec.gemini_content import GeminiContentCodec
from apix.agent.core.bot.codec.ollama_chat import OllamaChatCodec
from apix.agent.core.bot.codec.responses import ResponsesCodec

CODECS = {
    "chat_completions": ChatCompletionsCodec,
    "responses": ResponsesCodec,
    "messages": AnthropicMessagesCodec,
    "generate_content": GeminiContentCodec,
    "ollama_chat": OllamaChatCodec,
}
