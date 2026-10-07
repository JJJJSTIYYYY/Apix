from apix.agent.core.bot.base_bot import BaseOpenAIBot


class SiliconFlowBot(BaseOpenAIBot):
    """Constructor for SiliconFlow with registry-driven model behavior."""

    provider = "siliconflow"
