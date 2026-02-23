"""Structured JSON logger for GCP Cloud Logging ingestion.

Outputs JSON to stdout with severity, timestamp, and message fields
compatible with GCP Cloud Logging's structured log format.
"""

import json
import logging
import sys
from datetime import UTC, datetime


class StructuredJsonFormatter(logging.Formatter):
    """Format log records as JSON for GCP Cloud Logging."""

    SEVERITY_MAP: dict[int, str] = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            JSON string with severity, timestamp, message, and extra fields.
        """
        log_entry: dict[str, object] = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "severity": self.SEVERITY_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
        }

        # Include extra fields passed via the `extra` kwarg
        for key in ("batch_id", "stage", "duration_seconds", "error"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """Create a structured JSON logger.

    Args:
        name: Logger name, typically the module name.

    Returns:
        Configured logger that outputs JSON to stdout.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return logger
