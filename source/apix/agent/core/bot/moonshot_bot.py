from apix.agent.core.bot.base_bot import BaseOpenAIBot


class MoonshotBot(BaseOpenAIBot):
    """Constructor for Moonshot with registry-driven model behavior."""

    provider = "moonshot"
