"""
Simple structured JSON logging for the Task API.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore


class SimpleJsonFormatter(JsonFormatter):
    """Simple JSON formatter for structured logging."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add basic fields to the log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add basic timestamp and level
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        
        # Add any extra attributes from kwargs in the log call
        for key, value in record.__dict__.items():
            # Skip standard LogRecord attributes to avoid clutter
            if key not in logging.LogRecord.__dict__ and key not in [
                "args", "exc_info", "exc_text", "stack_info", "message"
            ]:
                # Only add JSON serializable types
                if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    log_record[key] = value


def get_logger(name: str = "task-api", log_level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a logger with JSON formatting.
    
    Args:
        name: The name of the logger
        log_level: The logging level (default: INFO)
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Create console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = SimpleJsonFormatter("%(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_request_logger(logger: logging.Logger, request_id: str, **context: Any) -> logging.LoggerAdapter[logging.Logger]:
    """
    Create a logger adapter with request context.
    
    Args:
        logger: The base logger to adapt
        request_id: The unique ID for the request
        context: Additional context to include in logs
        
    Returns:
        A logger adapter with request context
    """
    extra: Dict[str, Any] = {"request_id": request_id}
    
    # Add any additional context
    for key, value in context.items():
        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
            extra[key] = value
    
    return logging.LoggerAdapter(logger, extra)
