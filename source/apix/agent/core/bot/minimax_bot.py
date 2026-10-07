from apix.agent.core.bot.base_bot import BaseOpenAIBot


class MiniMaxBot(BaseOpenAIBot):
    """Compatibility constructor. Model behavior comes from the registry."""

    provider = "minimax"
