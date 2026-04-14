from typing import Tuple
import base64
import os
import yaml
from app.commons.logger import logger

# ==========================================================
# Yaml
# ==========================================================

def load_from_yaml(dir, key=None) -> dict | str:
    config = None
    try:
        with open(dir, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            logger.info("[load_from_yaml] load config from yaml file successfully.")
        if key:
            return config.get(key)
    except Exception as e:
        logger.error(f"[load_from_yaml] Error loading yaml file: {e}")
        raise
    # logger.info(f"[load_from_yaml] Load config from {dir}: {config}")
    return config

def write_to_yaml(dir, data: dict):
    try:
        with open(dir, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)
            logger.info("[write_to_yaml] write data to local yaml file successfully.")
    except Exception as e:
        logger.error(f"[write_to_yaml] Error writing to yaml file: {e}")
        raise

def append_to_yaml(dir, new_data: dict):
    try:
        if os.path.exists(dir):
            with open(dir, "r", encoding="utf-8") as f:
                existing_data = yaml.safe_load(f) or {}
        else:
            existing_data = {}

        # Update existing data with new data
        existing_data.update(new_data)

        with open(dir, "w", encoding="utf-8") as f:
            yaml.safe_dump(existing_data, f, allow_unicode=True)
            logger.info("[append_to_yaml] append data to local yaml file successfully.")
    except Exception as e:
        logger.error(f"[append_to_yaml] Error appending to yaml file: {e}")
        raise