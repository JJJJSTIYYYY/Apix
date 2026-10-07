from apix.agent.core.bot.base_bot import BaseOpenAIBot


class QwenBot(BaseOpenAIBot):
    """Constructor for Qwen with registry-driven model behavior."""

    provider = "qwen"
