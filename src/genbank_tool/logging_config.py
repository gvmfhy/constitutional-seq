"""Logging configuration and utilities."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors if enabled."""
        # Save original levelname
        levelname = record.levelname
        
        # Add color to levelname if colors are enabled
        if self.use_colors and levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        # Format the record
        result = super().format(record)
        
        # Restore original levelname
        record.levelname = levelname
        
        return result


class ProgressLogger:
    """Logger for progress tracking in batch operations."""
    
    def __init__(self, logger: logging.Logger, total: int, operation: str = "Processing"):
        """
        Initialize progress logger.
        
        Args:
            logger: Logger instance to use
            total: Total number of items
            operation: Operation description
        """
        self.logger = logger
        self.total = total
        self.operation = operation
        self.processed = 0
        self.failed = 0
        self.start_time = datetime.now()
    
    def update(self, success: bool = True, item: Optional[str] = None):
        """Update progress."""
        self.processed += 1
        if not success:
            self.failed += 1
        
        # Calculate progress
        progress = (self.processed / self.total) * 100 if self.total > 0 else 0
        
        # Calculate ETA
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.processed > 0 and elapsed > 0:
            rate = self.processed / elapsed
            remaining = (self.total - self.processed) / rate if rate > 0 else 0
            eta = f", ETA: {int(remaining)}s"
        else:
            eta = ""
        
        # Log progress
        if item:
            status = "✓" if success else "✗"
            self.logger.info(
                f"{self.operation}: {status} {item} "
                f"[{self.processed}/{self.total} ({progress:.1f}%){eta}]"
            )
        else:
            self.logger.info(
                f"{self.operation}: {self.processed}/{self.total} "
                f"({progress:.1f}%) - {self.failed} failed{eta}"
            )
    
    def complete(self):
        """Log completion summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        success_rate = ((self.processed - self.failed) / self.processed * 100) if self.processed > 0 else 0
        
        self.logger.info(
            f"{self.operation} complete: {self.processed} items in {elapsed:.1f}s "
            f"({success_rate:.1f}% success rate)"
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = ".genbank_logs",
    console: bool = True,
    colors: bool = True,
    rotate_logs: bool = True,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
    quiet: bool = False
) -> Dict[str, logging.Logger]:
    """
    Setup comprehensive logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Custom log file name
        log_dir: Directory for log files
        console: Enable console output
        colors: Enable colored console output
        rotate_logs: Enable log rotation
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        quiet: Suppress all but error logs to console
        
    Returns:
        Dictionary of configured loggers
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Determine log file
    if log_file is None:
        log_file = log_path / f"genbank_tool_{datetime.now().strftime('%Y%m%d')}.log"
    else:
        log_file = log_path / log_file
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        '%(levelname)s - %(message)s',
        use_colors=colors
    )
    
    # Remove existing handlers from root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure root logger
    root_logger.setLevel(logging.DEBUG)
    
    # File handler
    if rotate_logs:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
    else:
        file_handler = logging.FileHandler(log_file)
    
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        if quiet:
            console_handler.setLevel(logging.ERROR)
        else:
            console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Create specific loggers
    loggers = {
        'main': logging.getLogger('genbank_tool'),
        'gene_resolver': logging.getLogger('genbank_tool.gene_resolver'),
        'sequence_retriever': logging.getLogger('genbank_tool.sequence_retriever'),
        'transcript_selector': logging.getLogger('genbank_tool.transcript_selector'),
        'data_validator': logging.getLogger('genbank_tool.data_validator'),
        'cache': logging.getLogger('genbank_tool.cache'),
        'api': logging.getLogger('genbank_tool.api'),
        'error': logging.getLogger('genbank_tool.error'),
        'performance': logging.getLogger('genbank_tool.performance')
    }
    
    # Log startup message
    loggers['main'].info(f"Logging initialized - Level: {log_level}, File: {log_file}")
    
    return loggers


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(f"genbank_tool.{name}")


def log_api_call(api_name: str, endpoint: str, params: Dict[str, Any], response_time: float, success: bool):
    """Log API call details."""
    logger = logging.getLogger('genbank_tool.api')
    
    if success:
        logger.debug(
            f"API call: {api_name} - {endpoint} "
            f"(params: {params}, response_time: {response_time:.2f}s)"
        )
    else:
        logger.error(
            f"API call failed: {api_name} - {endpoint} "
            f"(params: {params}, response_time: {response_time:.2f}s)"
        )


def log_performance(operation: str, duration: float, items: Optional[int] = None):
    """Log performance metrics."""
    logger = logging.getLogger('genbank_tool.performance')
    
    if items:
        rate = items / duration if duration > 0 else 0
        logger.info(f"{operation}: {items} items in {duration:.2f}s ({rate:.1f} items/s)")
    else:
        logger.info(f"{operation}: completed in {duration:.2f}s")


def log_cache_hit(namespace: str, key: str, hit: bool):
    """Log cache access."""
    logger = logging.getLogger('genbank_tool.cache')
    
    if hit:
        logger.debug(f"Cache hit: {namespace}:{key}")
    else:
        logger.debug(f"Cache miss: {namespace}:{key}")


# Context manager for operation timing
class LogTimer:
    """Context manager for timing operations."""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        """
        Initialize timer.
        
        Args:
            operation: Operation description
            logger: Logger to use (defaults to performance logger)
        """
        self.operation = operation
        self.logger = logger or logging.getLogger('genbank_tool.performance')
        self.start_time = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log elapsed time."""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if exc_type is None:
                self.logger.debug(f"{self.operation} completed in {elapsed:.2f}s")
            else:
                self.logger.error(f"{self.operation} failed after {elapsed:.2f}s")


# Decorators for common logging patterns
def log_function_call(logger: Optional[logging.Logger] = None):
    """Decorator to log function calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(f"genbank_tool.{func.__module__}")
            
            logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__} returned successfully")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
                raise
        
        return wrapper
    return decorator


def log_execution_time(logger: Optional[logging.Logger] = None):
    """Decorator to log function execution time."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger('genbank_tool.performance')
            
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.debug(f"{func.__name__} executed in {elapsed:.2f}s")
                return result
            except Exception:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.debug(f"{func.__name__} failed after {elapsed:.2f}s")
                raise
        
        return wrapper
    return decorator