"""
MT5-AI-Trader Pro - Configuration Module

This module contains all configuration settings for the trading system.
Centralizes all constants, parameters, and environment-specific settings.

Author: MT5-AI-Trader Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path


# ===========================================
# MT5 Connection Configuration
# ===========================================
@dataclass
class MT5Config:
    """MetaTrader 5 connection settings."""
    login: int = 12345678
    password: str = ""
    server: str = "YourBroker-Server"
    path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    timeout: int = 60000  # milliseconds
    retry_attempts: int = 3


MT5_CONFIG = MT5Config()


# ===========================================
# Trading Configuration
# ===========================================
@dataclass
class TradingConfig:
    """Core trading settings."""
    symbol: str = "XAUUSD"
    timeframes: List[str] = field(default_factory=lambda: ["M5", "M15", "H1", "H4"])
    execution_timeframe: str = "M15"
    default_risk_percent: float = 1.0  # 1% risk per trade
    max_daily_loss_percent: float = 5.0  # 5% maximum daily loss
    max_open_trades: int = 3  # Maximum concurrent positions
    use_trailing_stop: bool = True
    min_reward_risk_ratio: float = 1.5  # Minimum R:R ratio


TRADING_CONFIG = TradingConfig()


# ===========================================
# Risk Management Configuration
# ===========================================
@dataclass
class RiskConfig:
    """Risk management parameters."""
    risk_per_trade: float = 1.0  # Percentage of account equity
    max_daily_loss: float = 5.0  # Percentage
    max_drawdown: float = 10.0  # Percentage (trading halt)
    max_position_size: float = 1.0  # Maximum lot size
    min_position_size: float = 0.01  # Minimum lot size
    atr_period: int = 14  # For SL/TP calculation
    sl_atr_multiplier: float = 2.0  # Stop Loss = 2 × ATR
    tp_atr_multiplier: float = 3.0  # Take Profit = 3 × ATR
    trailing_stop_activation: float = 1.0  # Activate after 1R profit
    trailing_stop_distance: float = 1.5  # Trail by 1.5 × ATR


RISK_CONFIG = RiskConfig()


# ===========================================
# Machine Learning Configuration
# ===========================================
@dataclass
class MLConfig:
    """Machine learning model settings."""
    # Model confidence threshold for trading
    confidence_threshold: float = 0.60  # Minimum 60% confidence
    
    # Ensemble weights
    ensemble_weight_xgb: float = 0.6  # XGBoost weight
    ensemble_weight_rf: float = 0.4   # RandomForest weight
    
    # Model paths
    model_dir: Path = Path(__file__).parent / "models" / "saved"
    xgboost_model_path: str = "xgboost_model.json"
    randomforest_model_path: str = "randomforest_model.pkl"
    
    # Training parameters
    test_size: float = 0.2
    validation_size: float = 0.2
    random_state: int = 42
    
    # Feature settings
    lookback_period: int = 100  # Bars for feature calculation
    min_samples: int = 1000  # Minimum samples for training


ML_CONFIG = MLConfig()


# ===========================================
# Database Configuration
# ===========================================
@dataclass
class DatabaseConfig:
    """SQLite database settings."""
    database_path: Path = Path(__file__).parent.parent / "database" / "trading.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24


DATABASE_CONFIG = DatabaseConfig()


# ===========================================
# Dashboard Configuration
# ===========================================
@dataclass
class DashboardConfig:
    """PyQt6 dashboard settings."""
    update_interval_ms: int = 1000  # Milliseconds
    chart_candles: int = 100  # Number of candles to display
    log_max_lines: int = 1000  # Maximum log lines in GUI
    theme: str = "dark"  # dark or light
    width: int = 1200
    height: int = 800


DASHBOARD_CONFIG = DashboardConfig()


# ===========================================
# Logging Configuration
# ===========================================
@dataclass
class LoggingConfig:
    """Logging settings."""
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Path = Path(__file__).parent.parent / "logs" / "trading.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    console_output: bool = True


LOGGING_CONFIG = LoggingConfig()


# ===========================================
# Communication Configuration
# ===========================================
@dataclass
class CommunicationConfig:
    """MQL5-Python communication settings."""
    # Shared memory / pipe settings
    shared_memory_name: str = "MT5_AI_TRADER_SHARED"
    pipe_name: str = "\\\\.\\pipe\\MT5_AI_TRADER_PIPE"
    message_timeout_ms: int = 5000
    heartbeat_interval_sec: int = 10


COMMUNICATION_CONFIG = CommunicationConfig()


# ===========================================
# Environment Configuration
# ===========================================
@dataclass
class EnvironmentConfig:
    """Environment-specific settings."""
    mode: str = "live"  # live, paper, backtest
    debug_mode: bool = False
    auto_restart: bool = True
    restart_on_error: bool = True
    notification_email: str = ""
    notification_telegram_bot: str = ""
    notification_telegram_chat_id: str = ""


ENVIRONMENT_CONFIG = EnvironmentConfig()


# ===========================================
# Timeframe Mapping (MT5 Constants)
# ===========================================
TIMEFRAME_MAP: Dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
    "W1": 10080,
    "MN1": 43200,
}


# ===========================================
# Order Type Mapping
# ===========================================
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5


# ===========================================
# Signal Types
# ===========================================
SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLOSE = "CLOSE"


# ===========================================
# Validation Functions
# ===========================================
def validate_config() -> bool:
    """
    Validate all configuration settings.
    
    Returns:
        bool: True if all configurations are valid, False otherwise.
    """
    # Validate risk parameters
    if not 0 < RISK_CONFIG.risk_per_trade <= 100:
        raise ValueError("Risk per trade must be between 0 and 100")
    
    if not 0 < TRADING_CONFIG.default_risk_percent <= 100:
        raise ValueError("Default risk percent must be between 0 and 100")
    
    # Validate ML thresholds
    if not 0 <= ML_CONFIG.confidence_threshold <= 1:
        raise ValueError("Confidence threshold must be between 0 and 1")
    
    # Validate ensemble weights
    total_weight = ML_CONFIG.ensemble_weight_xgb + ML_CONFIG.ensemble_weight_rf
    if abs(total_weight - 1.0) > 0.001:
        raise ValueError("Ensemble weights must sum to 1.0")
    
    return True


def get_config_summary() -> str:
    """
    Get a summary string of all configurations.
    
    Returns:
        str: Formatted configuration summary.
    """
    summary = []
    summary.append("=" * 50)
    summary.append("MT5-AI-Trader Pro - Configuration Summary")
    summary.append("=" * 50)
    summary.append(f"Symbol: {TRADING_CONFIG.symbol}")
    summary.append(f"Timeframes: {', '.join(TRADING_CONFIG.timeframes)}")
    summary.append(f"Risk per Trade: {RISK_CONFIG.risk_per_trade}%")
    summary.append(f"Max Daily Loss: {RISK_CONFIG.max_daily_loss}%")
    summary.append(f"Max Open Trades: {TRADING_CONFIG.max_open_trades}")
    summary.append(f"ML Confidence Threshold: {ML_CONFIG.confidence_threshold * 100}%")
    summary.append(f"Mode: {ENVIRONMENT_CONFIG.mode}")
    summary.append("=" * 50)
    return "\n".join(summary)


# ===========================================
# Initialize Configuration
# ===========================================
if __name__ == "__main__":
    print(get_config_summary())
    try:
        validate_config()
        print("✓ All configurations validated successfully!")
    except ValueError as e:
        print(f"✗ Configuration validation failed: {e}")
