import asyncio
import json
import os
import sys
from datetime import datetime
import time
import traceback
from typing import Any
import inspect

from apix.config.base_config import BASE_DIR, DEBUG_LEVEL, TRACE, MAX_LOG_FILE_SIZE


LOG_LEVELS = {
    "DEBUG": 0,
    "INFO": 1,
    "WARN": 2,
    "ERROR": 3,
}

def register_log_level(tag: str, priority: int, *, exist_ok: bool = False):
    """Register a custom log level.
    """
    global LOG_LEVELS
    if tag in LOG_LEVELS and not exist_ok:
        raise ValueError(f"Log level `{tag}` has been registered.")
    LOG_LEVELS[tag] = priority

def unregister_log_level(tag: str, *, missing_ok: bool = True):
    """Unregister a custom log level.
    """
    global LOG_LEVELS
    if tag in LOG_LEVELS and not missing_ok:
        raise ValueError(f"Log level `{tag}` is not been registered.")
    LOG_LEVELS.pop(tag)


class Logger:
    """
    Apix loggger
    """

    log_cache: dict[str, list] = {}
    log_cache_size: int = 0
    current_log_file_index: dict[str, int] = {}
    current_log_date: dict[str, str] = {}
    max_cache_size = 1 * 1024 * 1024
    flush_event = asyncio.Event()
    flush_task = None
    running = False
    cache_lock = asyncio.Lock()
    
    COLOR_CODES = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'purple': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'gray': '\033[90m',
        'light_gray': '\033[37m',
        'light_yellow': '\033[93;1m',
        'bold': '\033[1m',
        'underline': '\033[4m',
        'reset': '\033[0m'
    }
    
    LEVEL_COLORS = {
        'info': 'light_gray',
        'warning': 'yellow',
        'error': 'red',
        'exception': 'red',
        'success': 'green',
        'debug': 'cyan'
    }
    
    def __init__(self, name='Logger', show_time=True, show_level=True):
        """        
        Args:
            name (str): Logger name
            show_time (bool): If to show timestamp
            show_level (bool): If to show log level
        """
        self.name = name
        self.show_time = show_time
        self.show_level = show_level

    def _get_caller_info(self) -> tuple[str, str, str]:
        """
        Get caller module/class/function information.

        Returns:
            tuple[str, str, str]:
                (module_name, class_name, function_name)
        """
        frame = inspect.currentframe()
        if frame is None:
            return "UNKNOWN", "UNKNOWN", "UNKNOWN"

        try:
            # Skip current frame
            frame = frame.f_back

            while frame:
                self_obj = frame.f_locals.get("self")

                # Skip Logger internal methods
                if isinstance(self_obj, Logger):
                    frame = frame.f_back
                    continue

                module_name = frame.f_globals.get("__name__", "UNKNOWN")
                module_name = module_name.split(".")[-1]

                function_name = frame.f_code.co_name

                class_name = "GLOBAL"

                if "self" in frame.f_locals:
                    class_name = frame.f_locals["self"].__class__.__name__
                elif "cls" in frame.f_locals:
                    class_name = frame.f_locals["cls"].__name__

                return module_name, class_name, function_name

            return "UNKNOWN", "GLOBAL", "UNKNOWN"

        finally:
            del frame
    
    def _format_message(self, message, *args):
        if not args:
            return str(message)
        
        try:
            return message % args
        except (TypeError, ValueError):
            parts = [str(message)]
            parts.extend(str(arg) for arg in args)
            return ' '.join(parts)
    
    def _format_kwargs(self, **kwargs):
        if not kwargs:
            return ""
        
        parts = []
        for key, value in kwargs.items():
            if isinstance(value, (dict, list, tuple, set)):
                formatted_value = repr(value)
            elif isinstance(value, str):
                if ' ' in value:
                    formatted_value = f'"{value}"'
                else:
                    formatted_value = value
            else:
                formatted_value = str(value)
            
            parts.append(f"{key}={formatted_value}")
        
        return " | ".join(parts)
    
    def _get_formatted_message(self, level, message, *args, **kwargs):
        parts = []

        if self.show_time:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            parts.append(f"{timestamp}")

        parts.append(f"[{self.name}]")

        if self.show_level:
            parts.append(f"[{level.upper()}]")

        module_name, class_name, function_name = self._get_caller_info()

        parts.append(
            f"[{module_name} "
            f"{class_name} "
            f"{function_name}]:"
        )

        formatted_main = self._format_message(message, *args)
        parts.append(formatted_main)

        if kwargs:
            kwargs_str = self._format_kwargs(**kwargs)
            parts.append(f"({kwargs_str})")

        return " ".join(parts)
    
    def _colorize(self, text, color_name):
        color_code = self.COLOR_CODES.get(color_name, self.COLOR_CODES['white'])
        return f"{color_code}{text}{self.COLOR_CODES['reset']}"
    
    def _log(self, level, message, *args, color_name=None, **kwargs):
        if color_name is None:
            color_name = self.LEVEL_COLORS.get(level, 'white')
        
        formatted_message = self._get_formatted_message(level, message, *args, **kwargs)

        if Logger.log_cache.get(self.name) is None:
            Logger.log_cache[self.name] = []
        Logger.log_cache[self.name].append(formatted_message)
        Logger.log_cache_size = Logger.log_cache_size + len(formatted_message)
        if Logger.log_cache_size >= Logger.max_cache_size:
            Logger.flush_event.set()

        colored_message = self._colorize(formatted_message, color_name)
        
        print(colored_message, file=sys.stderr if level in ['error', 'exception'] else sys.stdout)
    
    def info(self, message, *args, **kwargs):
        if LOG_LEVELS['INFO'] < LOG_LEVELS[DEBUG_LEVEL]: 
            return
        self._log('info', message, *args, **kwargs)
    
    def warning(self, message, *args, **kwargs):
        if LOG_LEVELS['WARN'] < LOG_LEVELS[DEBUG_LEVEL]: 
            return
        self._log('warning', message, *args, **kwargs)
    
    def error(self, message, *args, **kwargs):
        if LOG_LEVELS['ERROR'] < LOG_LEVELS[DEBUG_LEVEL]: 
            return
        self._log('error', message, *args, **kwargs)
    
    def exception(self, message, *args, **kwargs):
        if LOG_LEVELS['ERROR'] < LOG_LEVELS[DEBUG_LEVEL]: 
            return
        self._log('error', message, *args, **kwargs)
    
    def success(self, message, *args, **kwargs):
        if LOG_LEVELS['INFO'] < LOG_LEVELS[DEBUG_LEVEL]: 
            return
        self._log('success', message, *args, **kwargs)
    
    def debug(self, message, *args, **kwargs):
        if LOG_LEVELS['DEBUG'] < LOG_LEVELS[DEBUG_LEVEL]: 
            return
        self._log('debug', message, *args, **kwargs)
    
    def custom(self, message, *args, level="DEBUG", color="light_yellow", **kwargs):
        if level not in LOG_LEVELS:
            return

        if LOG_LEVELS[level] < LOG_LEVELS[DEBUG_LEVEL]:
            return

        self._log(level.lower(), message, *args, color_name=color, **kwargs)
    
    def separator(self, length=50, char='-', color='light_yellow', *args, **kwargs):
        separator_line = char * length
        self.custom(separator_line, *args, level='SEPARATOR', color=color, **kwargs)
    
    def trace(self, message = None):
        if not TRACE: 
            return
        if not message: 
            message = 'Enter'
        self._log('debug', message)

    async def write_log(self, log_folder: str, log_file: str, message: Any):
        """
        Append message to log file.
        """

        await asyncio.to_thread(
            self._write_log_sync,
            log_folder,
            log_file,
            message
        )

    def _write_log_sync(
            self,
            log_folder: str,
            log_file: str,
            message: Any
    ):
        if not log_folder or not log_folder.strip():
            log_folder = "logs"

        if not log_file or not log_file.strip():
            log_file = str(time.time())

        log_dir = os.path.join(BASE_DIR, log_folder)

        os.makedirs(log_dir, exist_ok=True)

        if isinstance(message, dict):
            file_path = os.path.join(
                log_dir,
                f"{log_file}.jsonl"
            )
        else:
            file_path = os.path.join(
                log_dir,
                f"{log_file}.log"
            )

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False))
            f.write("\n")


    @classmethod
    async def start(cls):
        if cls.running:
            return

        cls.running = True
        cls.flush_task = asyncio.create_task(cls.flush_loop())

    @classmethod
    async def stop(cls):
        if not cls.running:
            return

        cls.running = False

        cls.flush_event.set()

        if cls.flush_task:
            await cls.flush_task

        await cls.flush()

    @classmethod
    async def flush_loop(cls):

        while cls.running:

            await cls.flush_event.wait()

            cls.flush_event.clear()

            try:
                await cls.flush()
            except Exception:
                traceback.print_exc()

        await cls.flush()

    @classmethod
    async def flush(cls):

        async with cls.cache_lock:
            if not cls.log_cache:
                return

            cache = cls.log_cache
            cls.log_cache = {}
            cls.log_cache_size = 0

        await asyncio.to_thread(
            cls._flush_to_disk,
            cache
        )
        
    @classmethod
    def _flush_to_disk(cls, cache: dict[str, list[str]]):
        """
        Flush log cache to disk in worker thread.
        """
        for logger_name, messages in cache.items():

            if not messages:
                continue

            log_dir = os.path.join(BASE_DIR, logger_name)

            os.makedirs(log_dir, exist_ok=True)

            log_file = cls._get_log_file(
                logger_name,
                log_dir
            )

            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n".join(messages))
                f.write("\n")

    @classmethod
    def _get_log_file(cls, logger_name: str, log_dir: str) -> str:
        """
        Get current writable log file.

        Rules:
        1. If current file size < MAX_LOG_FILE_SIZE, continue writing.
        2. If current file size >= MAX_LOG_FILE_SIZE, create next file.
        """
        today = datetime.now().strftime("%Y-%m-%d")

        # Reset index when date changes
        if cls.current_log_date.get(logger_name) != today:
            cls.current_log_date[logger_name] = today
            cls.current_log_file_index[logger_name] = 0

        index = cls.current_log_file_index.get(logger_name, 0)

        while True:
            if index == 0:
                filename = f"{today}.log"
            else:
                filename = f"{today}_{index}.log"

            log_file = os.path.join(log_dir, filename)

            # File does not exist yet
            if not os.path.exists(log_file):
                cls.current_log_file_index[logger_name] = index
                return log_file

            # Current file still writable
            if os.path.getsize(log_file) < MAX_LOG_FILE_SIZE:
                cls.current_log_file_index[logger_name] = index
                return log_file

            # Rotate
            index += 1



# Apix default logger.
logger = Logger(name="APIX", show_time=True, show_level=True)