"""Application logging backed by the shared Apixis logger."""

from apixis.core.utils.logger import (
    Logger,
    register_log_level,
    unregister_log_level,
)

logger = Logger("Apix")

__all__ = ["Logger", "logger", "register_log_level", "unregister_log_level"]
