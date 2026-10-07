"""Tests for Apix-specific configuration and shared configuration ownership."""

import os
import runpy

import pytest
from apixis.core.config import base as shared_config
from apixis.core.config import core_config

from apix.config import base_config


def test_business_settings_use_apixis_configuration():
    assert base_config._get_config is shared_config._get_config
    assert base_config.APIX_BASE_DIR == core_config.BASE_DIR
    assert base_config.SQLITE_DATABASE == shared_config._get_config(
        "DATA_STORE.sqlite.database",
        os.path.join(base_config.APIX_BASE_DIR, "sqlite", "apix.sqlite3"),
    )


@pytest.mark.parametrize("data_store", ["sqlite", "mysql"])
@pytest.mark.parametrize("cache_store", ["builtin", "redis"])
def test_storage_settings_ignore_legacy_remote_configuration(
    monkeypatch, data_store, cache_store
):
    monkeypatch.setattr(
        shared_config,
        "_config",
        {
            "REMOTE_GATEWAY": {"enable": True},
            "EVENT_CHANNEL": {"type": "kafka"},
            "DATA_STORE": {"type": data_store},
            "CACHE": {"store_type": cache_store},
        },
    )
    settings = runpy.run_path(base_config.__file__)
    assert settings["DATA_STORE_TYPE"] == data_store
    assert settings["CACHE_STORE_TYPE"] == cache_store
