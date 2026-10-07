"""Compatibility import path for the profile-driven Bot."""

from apix.agent.core.bot.bot import BaseBot
from apix.agent.core.bot.codec.base import dump as _model_dump
from apix.agent.core.bot.codec.base import read as _read


class BaseOpenAIBot(BaseBot):
    """Legacy constructor for an explicitly configured OpenAI-compatible endpoint."""

    provider = "custom"


__all__ = ["BaseBot", "BaseOpenAIBot", "_model_dump", "_read"]
