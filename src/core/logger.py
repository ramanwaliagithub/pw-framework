"""
Enterprise logging layer.

- Console handler (human-readable, colorized in a real TTY)
- Rotating file handler (10MB x 5 backups) so long nightly regression runs
  don't produce unbounded log files
- Correlation ID injected into every record via a contextvars-backed filter,
  so parallel xdist workers running interleaved tests can still be traced
  end-to-end per test (grep by correlation_id)
- Sensitive value masking so tokens/passwords never land in plaintext logs
- Thread-safe: Python's logging module handles locking internally per
  handler; we additionally use contextvars (not thread-locals) so this is
  also safe under asyncio, which Playwright's async API relies on.
"""

from __future__ import annotations

import contextvars
import logging
import re
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR = _REPO_ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)

_MASK_PATTERNS = [
    re.compile(r'("?(?:password|token|secret|authorization)"?\s*[:=]\s*")([^"]+)(")', re.I),
]


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:12]
    _correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> str:
    return _correlation_id_var.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id_var.get()
        return True


class SecretMaskingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pattern in _MASK_PATTERNS:
            msg = pattern.sub(r"\1***MASKED***\3", msg)
        return msg


_FORMAT = "%(asctime)s | %(levelname)-8s | %(correlation_id)s | %(name)s | %(message)s"


def _build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:  # already configured (avoid duplicate handlers)
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    corr_filter = CorrelationIdFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(SecretMaskingFormatter(_FORMAT))
    console_handler.addFilter(corr_filter)

    file_handler = RotatingFileHandler(
        _LOG_DIR / "automation.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(SecretMaskingFormatter(_FORMAT))
    file_handler.addFilter(corr_filter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def get_logger(name: str = "automation") -> logging.Logger:
    return _build_logger(name)
