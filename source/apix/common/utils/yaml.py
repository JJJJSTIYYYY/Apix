from pathlib import Path
import os
import yaml

from apix.common.utils.logger import logger

# ==========================================================
# Yaml
# ==========================================================

def load_from_yaml(dir, key=None) -> dict | str:
    """
    Load yaml file and optionally return a specific key.

    Args:
        dir (str): Path to yaml file.
        key (str, optional): Specific key to retrieve from yaml content.
            If provided, return config[key], otherwise return full config.

    Returns:
        dict | str:
            - Full yaml data (dict) if key is None
            - Value of the specified key if key is provided (may be None if key not found)

    Raises:
        Exception: If file reading or yaml parsing fails.
    """
    config = None
    try:
        if os.path.exists(dir):
            with open(dir, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        if key is not None:
            return config.get(key)
    
    except Exception as e:
        logger.error(f"Error loading yaml file: {e}")
        raise
    return config


def write_to_yaml(dir, data: dict):
    """
    Write data to yaml file (overwrite mode).

    Args:
        dir (str): Path to yaml file.
        data (dict): Data to be written into yaml.

    Returns:
        None

    Raises:
        Exception: If file writing fails.
    """
    try:
        if not os.path.exists(dir):
            Path(dir).parent.mkdir(parents=True, exist_ok=True)
        with open(dir, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)
    except Exception as e:
        logger.error(f"Error writing to yaml file: {e}")
        raise


def append_to_yaml(dir, new_data: dict):
    """
    Append (merge) data into yaml file.

    If file exists:
        - Load existing yaml data
        - Merge with new_data using dict.update()
    If file does not exist:
        - Create a new yaml file with new_data

    Args:
        dir (str): Path to yaml file.
        new_data (dict): New data to merge into existing yaml.

    Returns:
        None

    Raises:
        Exception: If file read/write or yaml parsing fails.
    """
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
    except Exception as e:
        logger.error(f"Error appending to yaml file: {e}")
        raise

def update_to_yaml(file_path: Path, title: str, content: str) -> dict:
    """
    Update or delete a key in yaml file.

    Args:
        file_path (Path): yaml file path
        title (str): memo title
        content (str): memo content, if empty -> delete

    Returns:
        dict: latest full yaml data
    """
    try:
        # Load existing data
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        if not content.strip():
            # Delete
            if title in data:
                del data[title]
        else:
            # Insert / Update
            data[title] = content

        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

        return data

    except Exception as e:
        logger.error(f"Error updating to yaml file: {e}")
        raise