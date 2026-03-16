#!/usr/bin/env python3
"""
JARVIS Logging System - Comprehensive logging with rotation and monitoring
"""
import os
import sys
import logging
import traceback
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
from functools import wraps
from typing import Callable, Any
import threading

# Get paths
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log files
MAIN_LOG = LOG_DIR / "jarvis.log"
ERROR_LOG = LOG_DIR / "errors.log"
DEBUG_LOG = LOG_DIR / "debug.log"
AUDIT_LOG = LOG_DIR / "audit.log"


class JarvisFormatter(logging.Formatter):
    """Custom formatter with color support for terminal"""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname

        if self.use_colors:
            color = self.COLORS.get(level, '')
            reset = self.COLORS['RESET']
            level_str = f"{color}{level:8}{reset}"
        else:
            level_str = f"{level:8}"

        # Add thread name if not main thread
        thread = ""
        if record.threadName != "MainThread":
            thread = f" [{record.threadName}]"

        # Format the message
        msg = f"{timestamp} | {level_str} | {record.name}{thread} | {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            msg += f"\n{self._format_exception(record.exc_info)}"

        return msg

    def _format_exception(self, exc_info):
        return ''.join(traceback.format_exception(*exc_info))


class JarvisLogger:
    """Central logging manager for JARVIS"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._loggers = {}
        self._setup_root_logger()

    def _setup_root_logger(self):
        """Setup the root JARVIS logger"""
        # Main logger
        self.root = logging.getLogger('jarvis')
        self.root.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.root.handlers = []

        # Console handler (INFO and above)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(JarvisFormatter(use_colors=True))
        self.root.addHandler(console)

        # Main log file (INFO and above, rotating)
        main_handler = RotatingFileHandler(
            MAIN_LOG,
            maxBytes=5*1024*1024,  # 5 MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(JarvisFormatter(use_colors=False))
        self.root.addHandler(main_handler)

        # Error log file (ERROR and above)
        error_handler = RotatingFileHandler(
            ERROR_LOG,
            maxBytes=2*1024*1024,  # 2 MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JarvisFormatter(use_colors=False))
        self.root.addHandler(error_handler)

        # Debug log file (all levels, daily rotation)
        debug_handler = TimedRotatingFileHandler(
            DEBUG_LOG,
            when='midnight',
            interval=1,
            backupCount=7,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(JarvisFormatter(use_colors=False))
        self.root.addHandler(debug_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a named logger"""
        full_name = f"jarvis.{name}"
        if full_name not in self._loggers:
            self._loggers[full_name] = logging.getLogger(full_name)
        return self._loggers[full_name]

    def audit(self, action: str, details: str = "", user: str = "system"):
        """Log audit events"""
        audit_logger = self.get_logger('audit')

        # Ensure audit file handler exists
        if not any(isinstance(h, logging.FileHandler) and 'audit' in str(h.baseFilename)
                   for h in audit_logger.handlers):
            handler = RotatingFileHandler(
                AUDIT_LOG,
                maxBytes=10*1024*1024,
                backupCount=10,
                encoding='utf-8'
            )
            handler.setFormatter(JarvisFormatter(use_colors=False))
            audit_logger.addHandler(handler)

        audit_logger.info(f"[{user}] {action}: {details}")


def get_logger(name: str = "main") -> logging.Logger:
    """Get a logger instance"""
    return JarvisLogger().get_logger(name)


def audit_log(action: str, details: str = "", user: str = "system"):
    """Log an audit event"""
    JarvisLogger().audit(action, details, user)


def log_exceptions(logger_name: str = "main"):
    """Decorator to log exceptions from functions"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger(logger_name)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Exception in {func.__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


def log_call(logger_name: str = "main", level: int = logging.DEBUG):
    """Decorator to log function calls"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger(logger_name)
            logger.log(level, f"Calling {func.__name__}")
            result = func(*args, **kwargs)
            logger.log(level, f"Completed {func.__name__}")
            return result
        return wrapper
    return decorator


class ExceptionHandler:
    """Context manager for exception handling with logging"""

    def __init__(self, logger_name: str = "main", reraise: bool = True,
                 fallback: Any = None, message: str = ""):
        self.logger = get_logger(logger_name)
        self.reraise = reraise
        self.fallback = fallback
        self.message = message
        self.exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.exception = exc_val
            msg = self.message or f"Exception occurred: {exc_val}"
            self.logger.error(msg, exc_info=(exc_type, exc_val, exc_tb))

            if not self.reraise:
                return True  # Suppress exception
        return False


def setup_crash_handler():
    """Setup global crash handler for unhandled exceptions"""
    logger = get_logger("crash")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log keyboard interrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

        # Also write to crash file
        crash_file = LOG_DIR / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(crash_file, 'w') as f:
            f.write(f"JARVIS Crash Report\n")
            f.write(f"Time: {datetime.now()}\n")
            f.write(f"Exception: {exc_type.__name__}: {exc_value}\n\n")
            f.write("Traceback:\n")
            f.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))

    sys.excepthook = handle_exception


# Initialize logger on import
_logger_instance = JarvisLogger()
