import logging
import os
from datetime import datetime
from pathlib import Path


# Global variable to track the shared log file
_shared_log_file = None
_file_handler = None


class ColorFormatter(logging.Formatter):
    """Formatter with ANSI color support for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Create a copy to avoid modifying the original record
        record_copy = logging.makeLogRecord(record.__dict__)
        
        levelname = record_copy.levelname
        color = self.COLORS.get(levelname, self.RESET)
        record_copy.levelname = f"{color}{levelname}{self.RESET}"
        record_copy.name = f"\033[34m{record_copy.name}\033[0m"  # Blue for logger name
        
        log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record_copy)


class PlainFormatter(logging.Formatter):
    """Plain formatter without any color codes."""
    
    def format(self, record):
        log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def _get_log_file_path(log_dir: str) -> str:
    """
    Get the log file path with m-d-y_h-m(_#).log format.
    If a file already exists for this minute, append a number.
    """
    now = datetime.now()
    timestamp = now.strftime("%m-%d-%y_%H-%M")  # m-d-y_h-m format
    
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Check if file exists
    base_log_file = os.path.join(log_dir, f"{timestamp}.log")
    if not os.path.exists(base_log_file):
        return base_log_file
    
    # If it exists, add a number
    counter = 1
    while True:
        numbered_log_file = os.path.join(log_dir, f"{timestamp}_{counter}.log")
        if not os.path.exists(numbered_log_file):
            return numbered_log_file
        counter += 1


def setup_logger(name: str, log_dir: str = None, use_color: bool = True) -> logging.Logger:
    """
    Setup a logger with console and shared file handlers.
    All loggers write to the same combined log file.
    
    Args:
        name: Logger name (module name)
        log_dir: Directory to save logs. If None, uses {cwd}/logs
        use_color: Whether to use colored output in console
    
    Returns:
        Configured logger instance
    """
    global _shared_log_file, _file_handler
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create console handler with color formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    if use_color:
        console_handler.setFormatter(ColorFormatter())
    else:
        console_handler.setFormatter(PlainFormatter())
    logger.addHandler(console_handler)
    
    # Create shared file handler (only once)
    if _file_handler is None:
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs")
        
        _shared_log_file = _get_log_file_path(log_dir)
        _file_handler = logging.FileHandler(_shared_log_file, encoding='utf-8')
        _file_handler.setLevel(logging.DEBUG)
        _file_handler.setFormatter(PlainFormatter())
    
    logger.addHandler(_file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get an existing logger with the given name."""
    return logging.getLogger(name)
