from apix.agent.core.bot.bot import BaseBot


class AnthropicBot(BaseBot):
    """Constructor for Anthropic Messages with registry-driven model behavior."""

    provider = "anthropic"
