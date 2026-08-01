"""Tests for remote configuration and distributed-mode validation."""

import pytest

from apix.config import base_config


def test_remote_config_requires_explicit_true(monkeypatch):
    local = {"REMOTE_GATEWAY": {"enable": False}}
    monkeypatch.setattr(
        base_config, "_load_from_remote", lambda **kwargs: pytest.fail("remote load")
    )
    monkeypatch.setattr(base_config, "_load_from_yaml", lambda path: local)

    assert base_config._load_config("config.yaml") is local


def test_enabled_remote_config_is_loaded_and_local_wins(monkeypatch):
    local = {
        "REMOTE_GATEWAY": {
            "enable": True,
            "base_url": "http://gateway",
            "config_endpoint": "/config",
        },
        "SERVER": {"worker_count": 4},
    }
    calls = []
    monkeypatch.setattr(base_config, "_load_from_yaml", lambda path: local)
    monkeypatch.setattr(
        base_config,
        "_load_from_remote",
        lambda **kwargs: calls.append(kwargs)
        or {"SERVER": {"worker_count": 2, "base_dir": "/remote"}},
    )

    result = base_config._load_config("config.yaml")

    assert calls == [{"base_url": "http://gateway", "endpoint": "/config"}]
    assert result["SERVER"] == {"worker_count": 4, "base_dir": "/remote"}


def test_remote_event_channel_is_ignored_when_local_section_is_missing(
    monkeypatch,
):
    local = {
        "REMOTE_GATEWAY": {
            "enable": True,
            "base_url": "http://gateway",
            "config_endpoint": "/config",
        }
    }
    remote = {
        "EVENT_CHANNEL": {
            "type": "rabbitmq",
            "rabbitmq": {"url": "amqp://shared-gateway-mailbox/"},
        },
        "SERVER": {"worker_count": 2},
    }
    monkeypatch.setattr(base_config, "_load_from_yaml", lambda path: local)
    monkeypatch.setattr(
        base_config,
        "_load_from_remote",
        lambda **kwargs: remote,
    )

    result = base_config._load_config("config.yaml")

    assert "EVENT_CHANNEL" not in result
    assert result["SERVER"] == {"worker_count": 2}
    assert remote["EVENT_CHANNEL"]["type"] == "rabbitmq"


def test_remote_event_channel_cannot_fill_partial_local_section(monkeypatch):
    local_event_channel = {
        "type": "kafka",
        "kafka": {"bootstrap_servers": ["node-a-broker:9092"]},
    }
    local = {
        "REMOTE_GATEWAY": {
            "enable": True,
            "base_url": "http://gateway",
            "config_endpoint": "/config",
        },
        "EVENT_CHANNEL": local_event_channel,
    }
    monkeypatch.setattr(base_config, "_load_from_yaml", lambda path: local)
    monkeypatch.setattr(
        base_config,
        "_load_from_remote",
        lambda **kwargs: {
            "EVENT_CHANNEL": {
                "type": "rabbitmq",
                "kafka": {"topic_prefix": "shared-mailbox"},
                "rabbitmq": {"url": "amqp://shared/"},
            }
        },
    )

    result = base_config._load_config("config.yaml")

    assert result["EVENT_CHANNEL"] == local_event_channel
    assert "topic_prefix" not in result["EVENT_CHANNEL"]["kafka"]
    assert "rabbitmq" not in result["EVENT_CHANNEL"]


@pytest.mark.parametrize("enable", [1, "true", None])
def test_remote_enable_must_be_boolean(monkeypatch, enable):
    monkeypatch.setattr(
        base_config,
        "_load_from_yaml",
        lambda path: {"REMOTE_GATEWAY": {"enable": enable}},
    )
    with pytest.raises(ValueError, match="must be a boolean"):
        base_config._load_config("config.yaml")


@pytest.mark.parametrize(
    ("data_store", "cache_store", "expected"),
    [
        ("sqlite", "redis", "DATA_STORE.type=sqlite"),
        ("mysql", "builtin", "CACHE.store_type=builtin"),
    ],
)
def test_remote_mode_rejects_single_node_backends(
    data_store, cache_store, expected
):
    config = {
        "REMOTE_GATEWAY": {"enable": True},
        "DATA_STORE": {"type": data_store},
        "CACHE": {"store_type": cache_store},
    }
    with pytest.raises(ValueError, match=expected):
        base_config._validate_config_compatibility(config)


def test_remote_mode_accepts_mysql_and_redis():
    base_config._validate_config_compatibility(
        {
            "REMOTE_GATEWAY": {"enable": True},
            "DATA_STORE": {"type": "mysql"},
            "CACHE": {"store_type": "redis"},
        }
    )


def test_remote_node_id_is_uuid4_hex():
    node_id = base_config._create_node_id(True)
    assert len(node_id) == 32
    assert int(node_id, 16) >= 0
    assert base_config._create_node_id(False) == "apix_service"


def test_external_channel_defaults_are_available():
    assert base_config.EVENT_CHANNEL_TYPE in {"kafka", "rabbitmq"}
    assert base_config.KAFKA_BOOTSTRAP_SERVERS
    assert base_config.RABBITMQ_URL.startswith("amqp")
