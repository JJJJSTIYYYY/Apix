"""Apix application settings backed by Apixis configuration."""

import os
from collections.abc import Mapping
from typing import Any, Literal

from apixis.core.config.base import _config, _get_config
from apixis.core.config.core_config import BASE_DIR


VERSION = "3.0.0"


def _validate_config_compatibility(config: Mapping[str, Any]) -> None:
    """Reject storage backends that cannot be shared by remote nodes."""
    remote = config.get("REMOTE_GATEWAY")
    if not isinstance(remote, Mapping) or remote.get("enable") is not True:
        return

    data_store = config.get("DATA_STORE", {})
    cache = config.get("CACHE", {})
    data_store_type = (
        data_store.get("type", "sqlite")
        if isinstance(data_store, Mapping)
        else "sqlite"
    )
    cache_store_type = (
        cache.get("store_type", "builtin")
        if isinstance(cache, Mapping)
        else "builtin"
    )
    conflicts: list[str] = []
    if data_store_type == "sqlite":
        conflicts.append("DATA_STORE.type=sqlite")
    if cache_store_type == "builtin":
        conflicts.append("CACHE.store_type=builtin")
    if conflicts:
        raise ValueError(
            "REMOTE_GATEWAY requires distributed storage backends; "
            + ", ".join(conflicts)
            + " cannot be used in remote node mode."
        )


_validate_config_compatibility(_config)


# Server
APIX_BASE_DIR = BASE_DIR
BASE_URL = _get_config("SERVER.base_url", "http://localhost:2712")
WORKER_COUNT = _get_config("SERVER.worker_count", 4)


_PROVIDER_BASE_URL = {
    "ollama:local": "http://localhost:11434",
    "ollama": "https://ollama.com",
    "openai": "https://api.openai.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "xiaomimimo": "https://api.xiaomimimo.com/v1",
    "minimax": "https://api.minimaxi.com/v1"
}

# Runtime
TOOLS_MAX_OUTPUT_LENGTH = _get_config(
    "RUNTIME.tools_max_output_length",
    32000,
)
MAX_RETRY = _get_config("RUNTIME.max_retry", 8)
GENERATION_TTL = _get_config("RUNTIME.generation_ttl", 600)
CONTAINER_TTL = _get_config("RUNTIME.container_ttl", 6000)
GRAPH_CACHE_TTL = _get_config("RUNTIME.graph_cache_ttl", 600)
CACHE_CLEAN_INTERVAL = _get_config("RUNTIME.cache_clean_interval", 300)


# Cache
CACHE_STORE_TYPE: Literal["builtin", "redis"] = _get_config(
    "CACHE.store_type",
    "builtin",
)
HOT_CACHE_DEFAULT_EXPIRE_SECONDS = _get_config(
    "CACHE.hot_cache_default_expire_seconds",
    600,
)
STATIC_CACHE_DEFAULT_EXPIRE_SECONDS = _get_config(
    "CACHE.static_cache_default_expire_seconds",
    604800,
)

MEMO_REDIS_URL = _get_config(
    "CACHE.redis.url",
    "redis://localhost:6379",
)
REDIS_POOL_SIZE = _get_config("CACHE.redis.pool_size", 3)


# Data store
DATA_STORE_TYPE: Literal["sqlite", "mysql"] = _get_config(
    "DATA_STORE.type",
    "sqlite",
)

SQLITE_DATABASE = _get_config(
    "DATA_STORE.sqlite.database",
    os.path.join(APIX_BASE_DIR, "sqlite", "apix.sqlite3"),
)

MYSQL_BASE_URL = _get_config("DATA_STORE.mysql.base_url", "localhost")
MYSQL_PORT = _get_config("DATA_STORE.mysql.port", 3307)
MYSQL_USER = _get_config("DATA_STORE.mysql.user", "apix")
MYSQL_PASSWORD = _get_config("DATA_STORE.mysql.password", "apixapix")
MYSQL_DATABASE = _get_config("DATA_STORE.mysql.database", "apix_database")
MYSQL_CHARSET = _get_config("DATA_STORE.mysql.charset", "utf8mb4")
AUTO_COMMIT = _get_config("DATA_STORE.mysql.auto_commit", True)


# LLM
PROVIDER_BASE_URL = _get_config(
    "LLM.provider_base_url",
    _PROVIDER_BASE_URL,
)
LLM_MAX_RETRY = _get_config("LLM.max_retry", 3)
LLM_TIMEOUT = _get_config("LLM.timeout", 30)
