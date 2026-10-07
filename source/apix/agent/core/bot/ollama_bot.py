from apix.agent.core.bot.bot import BaseBot


class OllamaBot(BaseBot):
    """Compatibility constructor for native Ollama chat."""

    provider = "ollama"
