"""Structured JSON-line logger for pipeline execution events."""

import json
import logging
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the log record message dict into a JSON line with required fields."""
        if isinstance(record.msg, dict):
            log_entry = dict(record.msg)
        else:
            log_entry = {"message": str(record.msg)}

        # Ensure required fields
        log_entry.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        log_entry.setdefault("level", record.levelname)

        return json.dumps(log_entry, default=str)


def get_logger(client_id: str, log_file: str | None = None) -> logging.Logger:
    """Return a JSON-line logger for the given client_id, creating handlers only once."""
    logger = logging.getLogger(client_id)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Stdout handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(JSONFormatter())
    logger.addHandler(stream_handler)

    # Optional file handler
    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)

    return logger


def log_event(logger: logging.Logger, event: str, client_id: str, **kwargs: Any) -> None:
    """Convenience function to log a structured event dict."""
    entry: dict[str, Any] = {
        "event": event,
        "client_id": client_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    entry.update(kwargs)
    logger.info(entry)
