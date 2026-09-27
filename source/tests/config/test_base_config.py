"""Tests for Apix-specific configuration and shared configuration ownership."""

import os

import pytest

from apix.config import base_config
from apixis.core.config import base as shared_config
from apixis.core.config import core_config


def test_business_settings_use_apixis_configuration():
    assert base_config._get_config is shared_config._get_config
    assert base_config.APIX_BASE_DIR == core_config.BASE_DIR
    assert base_config.SQLITE_DATABASE == shared_config._get_config(
        "DATA_STORE.sqlite.database",
        os.path.join(base_config.APIX_BASE_DIR, "sqlite", "apix.sqlite3"),
    )


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
