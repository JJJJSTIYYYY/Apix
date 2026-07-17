# Global configuration settings for the Apix.
VERSION = "3.0.0"

import os
import uuid
import platform

import yaml


def _load_from_yaml(dir, *, key=None) -> dict | str:
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
        raise
    return config

OPERATION_SYSTEM = platform.system().lower()
SERVER_ID = str(uuid.uuid4().hex)
ORIGINAL_PROXY_ENV = {
    "HTTP_PROXY": os.environ.get("HTTP_PROXY"),
    "HTTPS_PROXY": os.environ.get("HTTPS_PROXY"),
    "NO_PROXY": os.environ.get("NO_PROXY"),
}
BASE_DIR = "./data/" # Base log direction
SANDBOX_DOCKER_IMAGE_NAME = "apix-sandbox:latest" # Sandbox image name.
BASE_URL = {       # Base URL for the LLM service
    # Ollama
    'ollama:local': 'http://localhost:11434',  # Local
    'ollama': 'https://ollama.com',  # Cloud
    
    # OpenAI
    'openai': 'https://api.openai.com/v1',
    
    # Google (Gemini)
    'google': 'https://generativelanguage.googleapis.com',
    
    # Qwen (通义千问)
    'qwen': 'https://dashscope.aliyuncs.com/v1',
    
    # Qianfan (百度千帆)
    'qianfan': 'https://qianfan.baidubce.com/v1',
    
    # DeepSeek
    'deepseek': 'https://api.deepseek.com/v1',

    # Moonshot (月之暗面)
    'moonshot': 'https://api.moonshot.cn/v1',

    # XiaomiMIMO
    'xiaomimimo': 'https://api.xiaomimimo.com/v1',
}

_config = _load_from_yaml('./config.yaml')

EVENT_PIPE_MAX_LEN = _config.get('EVENT_PIPE_MAX_LEN', 1024)
EVENT_HANDLER_DEFAULT_TIME_OUT = _config.get('EVENT_HANDLER_DEFAULT_TIME_OUT', 300)
MESSAGE_PIPE_MAX_LEN = _config.get('MESSAGE_PIPE_MAX_LEN', 4096)
DEBUG = _config.get('DEBUG', True)
TRACE = _config.get('TRACE', True)
MAX_LOG_FILE_SIZE = _config.get('MAX_LOG_FILE_SIZE', 5 * 1024 * 1024)
TOOLS_MAX_OUTPUT_LENGTH = _config.get('TOOLS_MAX_OUTPUT_LENGTH', 32000)
MAX_RETRY = _config.get('MAX_RETRY', 8) # Max retry when llm_call failure, make sure it > 3

GENERATION_TTL = _config.get('GENERATION_TTL', 600) # Clear finished/aborted generation ctx (seconds)
CONTIANER_TTL = _config.get('CONTIANER_TTL', 6000)
GRAPH_CACHE_TTL = _config.get('GRAPH_CACHE_TTL', 600)
CACHE_CLEAN_INTERVAL = _config.get('CACHE_CLEAN_INTERVAL', 300)

MEMO_REDIS_URL = _config.get('MEMO_REDIS_URL', "redis://localhost:6379")
REDIS_POOL_SIZE = _config.get('REDIS_POOL_SIZE', 3)
DEFAULT_EXPIRE_SECONDS = _config.get('DEFAULT_EXPIRE_SECONDS', 600)

WORKER_COUNT = _config.get('WORKER_COUNT', 4) # Number of worker tasks in DataServerManager

MYSQL_DOCKER_BASE_URL = _config.get('MYSQL_DOCKER_BASE_URL', "localhost")
MYSQL_DOCKER_PORT = _config.get('MYSQL_DOCKER_PORT', 3307)
MYSQL_USER = _config.get('MYSQL_USER', "apix")
MYSQL_PASSWORD = _config.get('MYSQL_PASSWORD', "apixapix")
MYSQL_DATABASE = _config.get('MYSQL_DATABASE', "apix_database")
MYSQL_CHARSET = _config.get('MYSQL_CHARSET', "utf8mb4")
AUTO_COMMIT = _config.get('AUTO_COMMIT', True)