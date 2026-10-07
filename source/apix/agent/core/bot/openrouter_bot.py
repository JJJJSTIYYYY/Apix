from apix.agent.core.bot.base_bot import BaseOpenAIBot


class OpenRouterBot(BaseOpenAIBot):
    """Constructor for OpenRouter with registry-driven model behavior."""

    provider = "openrouter"
