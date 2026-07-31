"""Logging configuration for MT5-AI-Trader."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core.settings import AppSettings


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(settings: AppSettings) -> logging.Logger:
    """Configure console and rotating file logging for the application.

    The function is idempotent for the root logger: existing handlers are
    cleared before new handlers are attached, which prevents duplicate log lines
    during tests or repeated startup calls.
    """

    settings.log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(settings.log_level)

    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        settings.log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return logging.getLogger(settings.project_name)
