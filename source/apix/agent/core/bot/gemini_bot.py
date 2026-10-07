from apix.agent.core.bot.bot import BaseBot


class GeminiBot(BaseBot):
    """Constructor for Gemini GenerateContent with registry-driven model behavior."""

    provider = "gemini"
