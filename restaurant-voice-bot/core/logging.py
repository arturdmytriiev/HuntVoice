"""
Logging configuration with JSON formatter for structured logging.
"""
import logging
import sys
from typing import Any, Dict
from pythonjsonlogger import jsonlogger
from core.settings import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # Add application context
        log_record['app_name'] = settings.app_name
        log_record['environment'] = settings.app_env

        # Add exception info if present
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)


def setup_logging() -> None:
    """
    Configure application logging with JSON formatter.

    Sets up structured JSON logging for production environments
    and human-readable logging for development.
    """
    # Determine log format based on environment
    use_json = settings.app_env in ["production", "staging"]

    # Create formatter
    if use_json:
        formatter = CustomJsonFormatter(
            fmt='%(timestamp)s %(level)s %(name)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Set more verbose logging in development
    if settings.is_development:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    logging.info(
        "Logging configured",
        extra={
            "log_level": settings.log_level,
            "environment": settings.app_env,
            "json_logging": use_json
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: The name of the logger (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Context manager for adding context to logs
class LogContext:
    """Context manager for adding contextual information to logs."""

    def __init__(self, **kwargs: Any):
        """
        Initialize log context.

        Args:
            **kwargs: Key-value pairs to add to log context
        """
        self.context = kwargs
        self.logger = get_logger(__name__)

    def __enter__(self) -> 'LogContext':
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context."""
        if exc_type is not None:
            self.logger.error(
                f"Exception in context: {exc_type.__name__}",
                extra=self.context,
                exc_info=True
            )

    def log(self, level: str, message: str, **extra_fields: Any) -> None:
        """
        Log a message with context.

        Args:
            level: Log level (debug, info, warning, error, critical)
            message: Log message
            **extra_fields: Additional fields to include in log
        """
        log_method = getattr(self.logger, level.lower())
        merged_context = {**self.context, **extra_fields}
        log_method(message, extra=merged_context)
