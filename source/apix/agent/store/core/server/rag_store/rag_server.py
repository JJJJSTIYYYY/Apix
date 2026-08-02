import asyncio
import hashlib
import json
import shutil
from typing import Iterable
import mimetypes
import os
import uuid
from pathlib import Path
import zipfile
import yaml

from apix.common.utils.logger import logger
from apix.config.base_config import BASE_DIR


class RagService:
    """
    File system service.
    """
    pass



rag_server = RagService()