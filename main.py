"""Application entry point for MT5-AI-Trader Pro."""

from __future__ import annotations

from core.logging_config import configure_logging
from core.settings import load_settings


def main() -> None:
    """Start the trading application bootstrap sequence."""

    settings = load_settings()
    logger = configure_logging(settings)
    logger.info("Starting %s for %s", settings.project_name, settings.symbol)


if __name__ == "__main__":
    main()
