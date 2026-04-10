import sys
from datetime import datetime
from global_config import DEBUG, TRACE

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
        'gray': '\033[90m',          # dark gray (非常舒服)
        'light_gray': '\033[37m',    # light gray (INFO专用)
        'light_yellow': '\033[93;1m',
        'bold': '\033[1m',
        'underline': '\033[4m',
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
    
    def _format_message(self, message, *args):
        """格式化消息，支持类似 logging 的 % 格式化"""
        if not args:
            return str(message)
        
        try:
            # 尝试使用 % 格式化
            return message % args
        except (TypeError, ValueError):
            # 如果格式化失败，将消息和参数拼接
            parts = [str(message)]
            parts.extend(str(arg) for arg in args)
            return ' '.join(parts)
    
    def _format_kwargs(self, **kwargs):
        """将kwargs格式化为字符串"""
        if not kwargs:
            return ""
        
        parts = []
        for key, value in kwargs.items():
            # 处理不同类型的值
            if isinstance(value, (dict, list, tuple, set)):
                # 对于容器类型，使用repr以获得更详细的表示
                formatted_value = repr(value)
            elif isinstance(value, str):
                # 字符串类型，如果有空格则加引号
                if ' ' in value:
                    formatted_value = f'"{value}"'
                else:
                    formatted_value = value
            else:
                # 其他类型直接转字符串
                formatted_value = str(value)
            
            parts.append(f"{key}={formatted_value}")
        
        return " | ".join(parts)
    
    def _get_formatted_message(self, level, message, *args, **kwargs):
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
        
        # 格式化主消息（支持 % 格式化和多个参数）
        formatted_main = self._format_message(message, *args)
        parts.append(formatted_main)
        
        # 添加上下文字典（kwargs）
        if kwargs:
            kwargs_str = self._format_kwargs(**kwargs)
            parts.append(f"({kwargs_str})")
        
        return ' '.join(parts)
    
    def _colorize(self, text, color_name):
        """为文本添加颜色"""
        color_code = self.COLOR_CODES.get(color_name, self.COLOR_CODES['white'])
        return f"{color_code}{text}{self.COLOR_CODES['reset']}"
    
    def _log(self, level, message, *args, color_name=None, **kwargs):
        """通用日志方法"""
        if color_name is None:
            color_name = self.LEVEL_COLORS.get(level, 'white')
        
        formatted_message = self._get_formatted_message(level, message, *args, **kwargs)
        colored_message = self._colorize(formatted_message, color_name)
        
        # 输出到控制台
        print(colored_message, file=sys.stderr if level in ['error', 'exception'] else sys.stdout)
    
    def info(self, message, *args, **kwargs):
        """信息级别日志 - 蓝色"""
        if DEBUG: self._log('info', message, *args, **kwargs)
    
    def warning(self, message, *args, **kwargs):
        """警告级别日志 - 黄色"""
        if DEBUG: self._log('warning', message, *args, **kwargs)
    
    def error(self, message, *args, **kwargs):
        """错误级别日志 - 红色"""
        if DEBUG: self._log('error', message, *args, **kwargs)
    
    def exception(self, message, *args, **kwargs):
        """异常级别日志 - 红色"""
        if DEBUG: self._log('error', message, *args, **kwargs)
    
    def success(self, message, *args, **kwargs):
        """成功级别日志 - 绿色"""
        if DEBUG: self._log('success', message, *args, **kwargs)
    
    def debug(self, message, *args, **kwargs):
        """调试级别日志 - 青色"""
        if DEBUG: self._log('debug', message, *args, **kwargs)
    
    def custom(self, message, *args, level='CUSTOM', color='light_yellow', **kwargs):
        """自定义级别和颜色的日志"""
        if DEBUG: self._log(level, message, *args, color, **kwargs)
    
    # 为淡黄色输出提供便捷方法
    def light_yellow(self, message, *args, **kwargs):
        """淡黄色输出（自定义级别）"""
        if DEBUG: self.custom(message, *args, level='LIGHT_YELLOW', color='light_yellow', **kwargs)
    
    def separator(self, length=50, char='-', color='light_yellow', *args, **kwargs):
        """输出分隔线"""
        if DEBUG: 
            separator_line = char * length
            self.custom(separator_line, *args, level='SEPARATOR', color=color, **kwargs)
    
    def trace(self, message):
        """跟踪日志 - 青色"""
        '''统一格式 [文件名] [类名] [方法名] Enter'''
        if TRACE: self._log('debug', message)


# 使用示例
def use_case():
    # 创建日志记录器实例
    logger = Logger(name="AppLogger", show_time=True, show_level=True)
    
    # 1. 类似 logging 的 % 格式化
    logger.info("[FileService] conversion finished: %s", "/path/to/final.zip")
    logger.info("[FileService] user %s logged in from %s", "张三", "192.168.1.1")
    logger.warning("[API] %s took %dms (threshold: %dms)", "/users", 1250, 1000)
    logger.error("[DB] connection to %s:%d failed", "localhost", 5432)
    
    # 2. 直接传入对象（自动转为字符串）
    user_dict = {"id": 123, "name": "张三", "email": "zhangsan@example.com"}
    logger.info("[FileService] get dict: ", user_dict)  # 字典自动转为字符串
    logger.info("[FileService] get list: ", [1, 2, 3, 4, 5])  # 列表自动转为字符串
    logger.info("[FileService] get object: ", user_dict)  # 任何对象都会自动转为字符串
    
    # 3. 混合使用：主消息格式化 + 额外参数
    logger.info(
        "[FileService] conversion finished: %s", 
        final_zip_path,
        file_size_mb=2.5,
        compression_ratio=0.8,
        time_taken=1.23
    )
    
    # 4. 多个非格式化参数
    logger.info(
        "[FileService] processing files: ",
        "file1.txt",
        "file2.txt",
        "file3.txt",
        total_files=3,
        processed=2
    )
    
    # 5. 测试各种数据类型
    logger.debug("Debug with complex types: ", 
                [1, 2, 3], 
                {"a": 1, "b": 2}, 
                ("tuple", 123),
                user_id=12345,
                tags=("important", "urgent"))
    
    # 6. 异常日志
    try:
        result = 10 / 0
    except ZeroDivisionError as e:
        logger.exception("Caught exception: %s", e, 
                        operation="division",
                        dividend=10,
                        divisor=0)
    
    # 7. 分隔线
    logger.separator(char="=", length=60)
    
    # 8. 简化版日志器
    simple_logger = Logger(name="Simple", show_time=False, show_level=True)
    simple_logger.info("Simple logger message: ", {"key": "value"}, status="ok")


logger = Logger(name="AppLogger", show_time=True, show_level=True)

if __name__ == "__main__":
    final_zip_path = "/data/output/converted.zip"
    use_case()