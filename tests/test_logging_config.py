"""Tests for logging configuration."""

import logging
from pathlib import Path

from core.logging_config import configure_logging
from core.settings import AppSettings


def test_configure_logging_creates_log_file(tmp_path: Path) -> None:
    """Logging configuration should create a writable rotating log file."""

    settings = AppSettings(log_dir=tmp_path, log_file="test.log")
    logger = configure_logging(settings)

    logger.info("test message")

    assert settings.log_path.exists()
    assert len(logging.getLogger().handlers) == 2
