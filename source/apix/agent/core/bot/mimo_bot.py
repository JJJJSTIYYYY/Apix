from apix.agent.core.bot.base_bot import BaseOpenAIBot


class XiaomiMIMOBot(BaseOpenAIBot):
    """Compatibility constructor for the MiMo provider alias."""

    provider = "mimo"
