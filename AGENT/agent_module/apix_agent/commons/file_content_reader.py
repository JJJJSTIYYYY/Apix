from typing import Tuple
import base64
import os
import yaml
from apix_agent.commons.logger import logger

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

# ==========================================================
# Image
# ==========================================================

def image_to_base64(image_path: str) -> Tuple[str, str]:
    """
    Convert an image file to base64 string.

    Supported formats:
        .png, .jpg, .jpeg, .gif, .bmp, .webp

    Returns:
        (base64_string, mime_type)
    """

    allowed_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }

    ext = os.path.splitext(image_path)[1].lower()

    if ext not in allowed_types:
        raise ValueError(f"Unsupported image type: {ext}")

    mime_type = allowed_types[ext]

    try:
        # Read image as binary
        with open(image_path, "rb") as f:
            data = f.read()

        # Encode to base64
        base64_str = base64.b64encode(data).decode("utf-8")

        return base64_str, mime_type

    except Exception as e:
        raise e


# ==========================================================
# Audio
# ==========================================================

def audio_to_base64(audio_path: str) -> Tuple[str, str]:
    """
    Convert an audio file to base64 string.

    Supported formats:
        .mp3, .wav, .ogg, .m4a, .aac, .flac

    Returns:
        (base64_string, mime_type)
    """

    allowed_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
    }

    ext = os.path.splitext(audio_path)[1].lower()

    if ext not in allowed_types:
        raise ValueError(f"Unsupported audio type: {ext}")

    mime_type = allowed_types[ext]

    try:
        # Read audio as binary
        with open(audio_path, "rb") as f:
            data = f.read()

        # Encode to base64
        base64_str = base64.b64encode(data).decode("utf-8")

        return base64_str, mime_type

    except Exception as e:
        raise e


# ==========================================================
# Video
# ==========================================================

def video_to_base64(video_path: str) -> Tuple[str, str]:
    """
    Convert a video file to base64 string.

    Supported formats:
        .mp4, .webm, .mov, .avi, .mkv

    Returns:
        (base64_string, mime_type)
    """

    allowed_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
    }

    ext = os.path.splitext(video_path)[1].lower()

    if ext not in allowed_types:
        raise ValueError(f"Unsupported video type: {ext}")

    mime_type = allowed_types[ext]

    try:
        # Read video as binary
        with open(video_path, "rb") as f:
            data = f.read()

        # Encode to base64
        base64_str = base64.b64encode(data).decode("utf-8")

        return base64_str, mime_type

    except Exception as e:
        raise e
    
# ==========================================================
# Text Loader
# ==========================================================

def load_text(file_path: str) -> str:
    """
    Load text content from a supported text file.

    Supported formats:
        .txt, .md, .log, .json, .csv,
        .xml, .html, .htm,
        .py, .js, .ts,
        .yaml, .yml

    Returns:
        file content as string

    Raises:
        ValueError: if file extension is not supported
        Exception: if file reading fails
    """

    allowed_types = {
        ".txt",
        ".md",
        ".log",
        ".json",
        ".csv",
        ".xml",
        ".html",
        ".htm",
        ".py",
        ".js",
        ".ts",
        ".yaml",
        ".yml",
    }

    ext = os.path.splitext(file_path)[1].lower()

    if ext not in allowed_types:
        raise ValueError(f"Unsupported text file type: {ext}")

    try:
        # Try reading with utf-8
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    except UnicodeDecodeError:
        # Fallback for files with BOM
        with open(file_path, "r", encoding="utf-8-sig") as f:
            return f.read()

    except Exception as e:
        raise e
    
