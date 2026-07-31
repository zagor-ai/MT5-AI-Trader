"""Application settings for MT5-AI-Trader.

This module keeps runtime configuration in one typed object so future modules
(strategy, execution, risk, news, and AI) can depend on a stable contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    """Typed application settings used by the trading system."""

    project_name: str = "MT5-AI-Trader Pro"
    symbol: str = "XAUUSD"
    environment: str = "development"
    log_level: str = "INFO"
    log_dir: Path = Path("logs")
    log_file: str = "mt5_ai_trader.log"

    @property
    def log_path(self) -> Path:
        """Return the full log file path for the configured environment."""

        return self.log_dir / self.log_file


def load_settings() -> AppSettings:
    """Load application settings.

    Environment-variable loading is intentionally deferred until Sprint 2 so the
    first sprint has a deterministic, testable baseline.
    """

    return AppSettings()
