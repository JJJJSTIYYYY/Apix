import json
import os
import sys
from datetime import datetime
import time
from typing import Any

from app.global_config import BASE_DIR, DEBUG, TRACE

class Logger:
    """
    彩色控制台日志输出类
    支持不同级别的日志输出，每种级别有不同颜色
    """
    
    # ANSI 颜色代码
    COLOR_CODES = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'purple': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'gray': '\033[90m',          # dark gray (very舒服)
        'light_gray': '\033[37m',    # light gray (INFO专用)
        'light_yellow': '\033[93;1m',
        'reset': '\033[0m'
    }
    
    # 日志级别与颜色映射
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
        初始化日志记录器
        
        Args:
            name (str): 日志记录器名称
            show_time (bool): 是否显示时间戳
            show_level (bool): 是否显示日志级别
        """
        self.name = name
        self.show_time = show_time
        self.show_level = show_level
    
    def _get_formatted_message(self, level, message):
        """格式化日志消息"""
        parts = []
        
        # 添加时间戳
        if self.show_time:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            parts.append(f"[{timestamp}]")
        
        # 添加日志记录器名称
        parts.append(f"[{self.name}]")
        
        # 添加日志级别
        if self.show_level:
            parts.append(f"[{level.upper()}]")
        
        # 添加消息内容
        parts.append(str(message))
        
        return ' '.join(parts)
    
    def _colorize(self, text, color_name):
        """为文本添加颜色"""
        color_code = self.COLOR_CODES.get(color_name, self.COLOR_CODES['white'])
        return f"{color_code}{text}{self.COLOR_CODES['reset']}"
    
    def _log(self, level, message, color_name=None):
        """通用日志方法"""
        if color_name is None:
            color_name = self.LEVEL_COLORS.get(level, 'white')
        
        formatted_message = self._get_formatted_message(level, message)
        colored_message = self._colorize(formatted_message, color_name)
        
        # 输出到控制台
        print(colored_message, file=sys.stderr if level in ['error', 'exception'] else sys.stdout)
    
    def info(self, message):
        """信息级别日志 - 蓝色"""
        if DEBUG: self._log('info', message)
    
    def warning(self, message):
        """警告级别日志 - 黄色"""
        self._log('warning', message)
    
    def error(self, message):
        """错误级别日志 - 红色"""
        self._log('error', message)
    
    def exception(self, message):
        """异常级别日志 - 红色"""
        self._log('error', message)
    
    def success(self, message):
        """成功级别日志 - 绿色"""
        if DEBUG: self._log('success', message)
    
    def debug(self, message):
        """调试级别日志 - 青色"""
        if DEBUG: self._log('debug', message)
    
    def trace(self, message):
        """跟踪日志 - 青色"""
        '''统一格式 [文件名] [类名] [方法名] Enter'''
        if TRACE: self._log('debug', message)
    
    def custom(self, message, level='CUSTOM', color='light_yellow'):
        """自定义级别和颜色的日志"""
        if DEBUG: self._log(level, message, color)
    
    # 为淡黄色输出提供便捷方法
    def light_yellow(self, message):
        """淡黄色输出（自定义级别）"""
        if DEBUG: self.custom(message, 'LIGHT_YELLOW', 'light_yellow')
    
    def separator(self, length=50, char='-', color='light_yellow'):
        """输出分隔线"""
        if DEBUG: 
            separator_line = char * length
            self.custom(separator_line, 'SEPARATOR', color)

    async def write_log(self, log_folder: str, log_file: str, message: Any):
        """append message to log file"""
        if not log_folder or not log_folder.strip():
            log_folder = "logs"
        if not log_file or not log_file.strip():
            log_file = str(time.time())
        log_dir = os.path.join(BASE_DIR, log_folder)
        os.makedirs(log_dir, exist_ok=True)
        if isinstance(message, dict):
            log_file = os.path.join(log_dir, f"{log_file}.jsonl")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")
        else:
            log_file = os.path.join(log_dir, f"{log_file}.log")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")




logger = Logger(name="AppLogger", show_time=True, show_level=True)