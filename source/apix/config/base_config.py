import os
import platform
from uuid import uuid4
from collections.abc import Mapping
from typing import Any, Literal

import httpx
import yaml


# Global configuration settings for Apix.
VERSION = "3.0.0"


def _load_from_yaml(path: str) -> dict[str, Any]:
    """Load configuration from a local YAML file."""
    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(
            f"Config file must contain a YAML mapping, got {type(data).__name__}."
        )

    return data


def _load_from_remote(
    base_url: str,
    endpoint: str,
) -> dict[str, Any]:
    """Load configuration from the remote config center."""
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    response = httpx.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(
            "Remote config center must return a JSON object, "
            f"got {type(data).__name__}."
        )

    return data


def _merge_config(
    remote: Mapping[str, Any],
    local: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Recursively merge configuration mappings.

    Local values always take precedence over remote values. Nested mappings
    are merged recursively, so a local partial section does not discard other
    remote values in that section.
    """
    merged = dict(remote)

    for key, local_value in local.items():
        remote_value = merged.get(key)

        if (
            isinstance(remote_value, Mapping)
            and isinstance(local_value, Mapping)
        ):
            merged[key] = _merge_config(remote_value, local_value)
        else:
            merged[key] = local_value

    return merged


def _load_config(path: str) -> dict[str, Any]:
    """
    Load the effective configuration.

    Loading order:
        1. Read local YAML.
        2. Discover REMOTE_GATEWAY from the local YAML.
        3. Load remote configuration when configured.
        4. Merge local configuration over remote configuration.
    """
    local_config = _load_from_yaml(path)

    remote_center = local_config.get("REMOTE_GATEWAY")
    if remote_center is None:
        return local_config

    if not isinstance(remote_center, Mapping):
        raise ValueError("REMOTE_GATEWAY must be a mapping.")

    enable = remote_center.get("enable", False)
    if not isinstance(enable, bool):
        raise ValueError("REMOTE_GATEWAY.enable must be a boolean.")
    if enable is not True:
        return local_config

    center_base_url = remote_center.get("base_url")
    config_endpoint = remote_center.get("config_endpoint")

    if not isinstance(center_base_url, str) or not center_base_url.strip():
        raise ValueError(
            "REMOTE_GATEWAY.base_url must be a non-empty string."
        )

    if not isinstance(config_endpoint, str) or not config_endpoint.strip():
        raise ValueError(
            "REMOTE_GATEWAY.config_endpoint must be a non-empty string."
        )

    remote_config = _load_from_remote(
        base_url=center_base_url,
        endpoint=config_endpoint,
    )

    return _merge_config(
        remote=remote_config,
        local=local_config,
    )


def _get_config(path: str, default=None):
    value = _config

    for key in path.split("."):
        if not isinstance(value, Mapping):
            return default

        if key not in value:
            return default

        value = value[key]

    return default if value is None else value


OPERATION_SYSTEM = platform.system().lower()

_DEFAULT_PROXY_ENV = {
    "HTTP_PROXY": os.environ.get("HTTP_PROXY"),
    "HTTPS_PROXY": os.environ.get("HTTPS_PROXY"),
    "NO_PROXY": os.environ.get("NO_PROXY"),
}

_PROVIDER_BASE_URL = {
    "ollama:local": "http://localhost:11434",
    "ollama": "https://ollama.com",
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com",
    "qwen": "https://dashscope.aliyuncs.com/v1",
    "qianfan": "https://qianfan.baidubce.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "xiaomimimo": "https://api.xiaomimimo.com/v1",
}

_config = _load_config("./config.yaml")


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


# Remote gateway and node identity
REMOTE_GATEWAY_ENABLE = _get_config("REMOTE_GATEWAY.enable", False) is True
REMOTE_GATEWAY_BASE_URL = _get_config(
    "REMOTE_GATEWAY.base_url", "http://localhost:8080"
)
REMOTE_GATEWAY_CONFIG_ENDPOINT = _get_config(
    "REMOTE_GATEWAY.config_endpoint", "/api/config"
)
REMOTE_GATEWAY_PIPE_ENDPOINT = _get_config(
    "REMOTE_GATEWAY.pipe_endpoint", "/api/pipe"
)
GATEWAY_MAX_RETRY = _get_config("REMOTE_GATEWAY.max_retry", 5)
GATEWAY_RETRY_INITIAL_DELAY = _get_config(
    "REMOTE_GATEWAY.retry_initial_delay", 1.0
)
GATEWAY_TIMEOUT = _get_config("REMOTE_GATEWAY.timeout", 10.0)


def _create_node_id(remote_enabled: bool) -> str:
    """Create a globally unique MQ id only for remote node mode."""
    return uuid4().hex if remote_enabled else "apix_service"


NODE_ID = _create_node_id(REMOTE_GATEWAY_ENABLE)


# Server
BASE_URL = _get_config("SERVER.base_url", "http://localhost:2712")
BASE_DIR = _get_config("SERVER.base_dir", "./.apix_data/")
WORKER_COUNT = _get_config("SERVER.worker_count", 4)
NODE_NAME = _get_config("SERVER.node_name", "apix_service")


# Proxy
_proxy_env_config = _get_config("PROXY.original_proxy_env", {})

if not isinstance(_proxy_env_config, Mapping):
    raise ValueError("PROXY.original_proxy_env must be a mapping.")

ORIGINAL_PROXY_ENV = {
    "HTTP_PROXY": _proxy_env_config.get(
        "http_proxy",
        _DEFAULT_PROXY_ENV["HTTP_PROXY"],
    ),
    "HTTPS_PROXY": _proxy_env_config.get(
        "https_proxy",
        _DEFAULT_PROXY_ENV["HTTPS_PROXY"],
    ),
    "NO_PROXY": _proxy_env_config.get(
        "no_proxy",
        _DEFAULT_PROXY_ENV["NO_PROXY"],
    ),
}


# Log
DEBUG_LEVEL: Literal["DEBUG", "INFO", "WARN", "ERROR"] = _get_config(
    "LOG.debug_level",
    "DEBUG",
).upper()

TRACE = _get_config("LOG.trace", True)
MAX_LOG_FILE_SIZE = _get_config("LOG.max_log_file_size", 5 * 1024 * 1024)


# Pipeline
EVENT_PIPE_MAX_LEN = _get_config("PIPELINE.event_pipe_max_len", 1024)
EVENT_HANDLER_DEFAULT_TIME_OUT = _get_config(
    "PIPELINE.event_handler_default_time_out",
    300,
)
MESSAGE_PIPE_MAX_LEN = _get_config("PIPELINE.message_pipe_max_len", 4096)


# External event mailbox
EVENT_CHANNEL_TYPE: Literal["kafka", "rabbitmq"] = _get_config(
    "EVENT_CHANNEL.type", "kafka"
)
KAFKA_BOOTSTRAP_SERVERS = _get_config(
    "EVENT_CHANNEL.kafka.bootstrap_servers", ["localhost:9092"]
)
KAFKA_TOPIC_PREFIX = _get_config(
    "EVENT_CHANNEL.kafka.topic_prefix", "apix.mailbox"
)
KAFKA_GROUP_ID_PREFIX = _get_config(
    "EVENT_CHANNEL.kafka.group_id_prefix", "apix.node"
)
RABBITMQ_URL = _get_config(
    "EVENT_CHANNEL.rabbitmq.url", "amqp://guest:guest@localhost/"
)
RABBITMQ_EXCHANGE = _get_config(
    "EVENT_CHANNEL.rabbitmq.exchange", "apix.events"
)
RABBITMQ_QUEUE_PREFIX = _get_config(
    "EVENT_CHANNEL.rabbitmq.queue_prefix", "apix.mailbox"
)
RABBITMQ_PREFETCH_COUNT = _get_config(
    "EVENT_CHANNEL.rabbitmq.prefetch_count", 100
)


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
    os.path.join(BASE_DIR, "sqlite", "apix.sqlite3"),
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
