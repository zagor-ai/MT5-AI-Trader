"""Tests for application settings."""

from pathlib import Path

from core.settings import AppSettings, load_settings


def test_default_settings_target_xauusd() -> None:
    """Default settings should target the project trading symbol."""

    settings = load_settings()

    assert settings.project_name == "MT5-AI-Trader Pro"
    assert settings.symbol == "XAUUSD"
    assert settings.environment == "development"


def test_log_path_uses_configured_directory_and_file() -> None:
    """Log path should be derived from log directory and file name."""

    settings = AppSettings(log_dir=Path("custom_logs"), log_file="app.log")

    assert settings.log_path == Path("custom_logs/app.log")
