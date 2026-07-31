# MT5-AI-Trader Pro

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![MT5](https://img.shields.io/badge/Platform-MetaTrader%205-orange.svg)

**Professional AI-Powered Trading System for MetaTrader 5**

*Focused on XAUUSD (Gold) Trading with Machine Learning & Risk Management*

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Trading Logic](#trading-logic)
- [AI Models](#ai-models)
- [Risk Management](#risk-management)
- [Dashboard](#dashboard)
- [Development Roadmap](#development-roadmap)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## 🎯 Overview

MT5-AI-Trader Pro is a professional-grade algorithmic trading system designed for MetaTrader 5, leveraging advanced machine learning techniques to generate high-probability trading signals for XAUUSD (Gold).

### Key Capabilities

- **Real-time Market Data Analysis**: Connects directly to MT5 for live price feeds
- **Multi-Timeframe Analysis**: Simultaneous analysis across M5, M15, H1, H4
- **Advanced Technical Indicators**: EMA, DEMA, RSI, MACD, ATR, ADX, Ichimoku, Bollinger Bands
- **Machine Learning Predictions**: XGBoost & RandomForest ensemble models
- **Professional Risk Management**: Position sizing, stop-loss, take-profit, trailing stops
- **Comprehensive Dashboard**: Real-time monitoring with PyQt6 GUI
- **Database Logging**: SQLite storage for all trades, signals, and performance metrics

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MT5 Terminal                              │
│                     (Market Data Source)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ IPC / Shared Memory
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MQL5 Expert Advisor                           │
│  • Order Execution    • Position Management    • Risk Control   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Communication Layer
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python AI Engine                              │
│  • Feature Engineering    • ML Models    • Decision Engine      │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌───────────────┐
│   Database    │   │    Dashboard    │   │  Risk Manager │
│   (SQLite)    │   │    (PyQt6)      │   │   (Module)    │
└───────────────┘   └─────────────────┘   └───────────────┘
```

### Component Flow

1. **MT5 Terminal** → Provides real-time market data
2. **MQL5 EA** → Bridges MT5 with Python, executes trades
3. **Communication Layer** → Handles data exchange between MQL5 and Python
4. **Feature Engineering** → Calculates technical indicators
5. **ML Models** → Generates BUY/SELL/HOLD probabilities
6. **Decision Engine** → Combines model outputs into trading decisions
7. **Risk Manager** → Validates trades against risk parameters
8. **Execution** → Sends orders back to MT5

---

## ✨ Features

### Core Features

- ✅ **Multi-Timeframe Analysis**: M5, M15, H1, H4 simultaneous processing
- ✅ **Technical Indicators**: 8+ professional indicators
- ✅ **Ensemble ML Models**: XGBoost + RandomForest voting
- ✅ **Probability Output**: Confidence scores for each direction
- ✅ **Risk Management**: 1% default risk per trade (configurable)
- ✅ **Position Sizing**: Dynamic lot calculation based on account balance
- ✅ **Stop Loss & Take Profit**: Automatic calculation using ATR
- ✅ **Trailing Stop**: Dynamic stop adjustment for profit protection
- ✅ **Daily Loss Limit**: Maximum drawdown protection
- ✅ **Trade Logging**: Complete audit trail in SQLite database
- ✅ **Real-time Dashboard**: Live monitoring with PyQt6 GUI

### Advanced Features (Roadmap)

- 🔄 **Reinforcement Learning**: PPO & SAC algorithms (Phase 2)
- 🔄 **LLM Integration**: News sentiment analysis (Phase 3)
- 🔄 **Market Correlation**: DXY, EURUSD, USDJPY context
- 🔄 **Backtesting Engine**: Historical performance validation
- 🔄 **Cloud Deployment**: Docker & Kubernetes support

---

## 📦 Installation

### Prerequisites

- **MetaTrader 5** installed on Windows
- **Python 3.10+**
- **pip** package manager

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/MT5-AI-Trader-Pro.git
cd MT5-AI-Trader-Pro
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure MT5 Connection

Edit `Python/config.py`:

```python
MT5_CONFIG = {
    "login": 12345678,
    "password": "your_password",
    "server": "YourBroker-Server",
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
}
```

### Step 4: Install MQL5 Expert Advisor

1. Copy `MQL5/Experts/AI_Trader_EA.mq5` to your MT5 Experts folder
2. Compile in MetaEditor
3. Attach to XAUUSD chart

---

## 📁 Project Structure

```
MT5-AI-Trader-Pro/
│
├── MQL5/
│   └── Experts/
│       └── AI_Trader_EA.mq5          # Main EA for MT5
│
├── Python/
│   ├── main.py                       # Application entry point
│   ├── config.py                     # Configuration settings
│   │
│   ├── mt5/
│   │   ├── connection.py             # MT5 connection handler
│   │   ├── market_data.py            # Market data collector
│   │   └── execution.py              # Trade execution module
│   │
│   ├── features/
│   │   ├── indicators.py             # Technical indicator calculations
│   │   └── feature_engineering.py    # Feature preparation for ML
│   │
│   ├── models/
│   │   ├── xgboost_model.py          # XGBoost classifier
│   │   ├── randomforest_model.py     # RandomForest classifier
│   │   └── risk/                     # Future RL models
│   │
│   ├── risk/
│   │   └── risk_manager.py           # Risk management logic
│   │
│   ├── database/
│   │   └── database.py               # SQLite database operations
│   │
│   └── dashboard/
│       └── gui.py                    # PyQt6 dashboard
│
├── tests/                            # Unit & integration tests
├── docs/                             # Documentation files
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
```

---

## ⚙️ Configuration

### Main Configuration (`config.py`)

```python
# Trading Settings
SYMBOL = "XAUUSD"
TIMEFRAMES = ["M5", "M15", "H1", "H4"]
DEFAULT_RISK_PERCENT = 1.0  # 1% risk per trade

# Risk Parameters
MAX_DAILY_LOSS = 5.0        # 5% maximum daily loss
MAX_OPEN_TRADES = 3         # Maximum concurrent positions
USE_TRAILING_STOP = True    # Enable trailing stop

# Model Settings
MODEL_CONFIDENCE_THRESHOLD = 0.60  # Minimum confidence to trade
ENSEMBLE_WEIGHT_XGB = 0.6           # XGBoost weight
ENSEMBLE_WEIGHT_RF = 0.4            # RandomForest weight

# Database
DATABASE_PATH = "trading.db"

# Dashboard
DASHBOARD_UPDATE_INTERVAL = 1000  # milliseconds
```

---

## 🚀 Usage

### Starting the System

1. **Launch MT5** and ensure you're logged in
2. **Attach AI_Trader_EA** to XAUUSD chart
3. **Run Python Engine**:

```bash
cd Python
python main.py
```

4. **Open Dashboard** (optional):

```bash
python dashboard/gui.py
```

### Command Line Options

```bash
python main.py --mode live          # Live trading
python main.py --mode paper         # Paper trading (simulation)
python main.py --mode backtest      # Backtesting mode
python main.py --symbol XAUUSD      # Change symbol
python main.py --risk 0.5           # Change risk percentage
```

---

## 📊 Trading Logic

### Symbol & Timeframes

- **Primary Symbol**: XAUUSD (Gold)
- **Analysis Timeframes**: M5, M15, H1, H4
- **Execution Timeframe**: M15 (default, configurable)

### Technical Indicators

| Indicator | Period | Purpose |
|-----------|--------|---------|
| EMA | 9, 21, 50, 200 | Trend direction |
| DEMA | 21 | Fast trend confirmation |
| RSI | 14 | Overbought/oversold |
| MACD | 12, 26, 9 | Momentum |
| ATR | 14 | Volatility (SL/TP calculation) |
| ADX | 14 | Trend strength |
| Ichimoku | 9, 26, 52 | Support/resistance |
| Bollinger Bands | 20, 2 | Volatility bands |

### Market Context

Future versions will incorporate:
- **DXY** (Dollar Index) correlation
- **EURUSD** trend confirmation
- **USDJPY** risk sentiment
- **News Sentiment** via LLM analysis

---

## 🤖 AI Models

### Phase 1: Supervised Learning (Current)

#### XGBoost Model
- **Type**: Gradient Boosting Classifier
- **Features**: 50+ engineered features
- **Output**: Probability distribution [BUY, SELL, HOLD]
- **Training**: Historical data with walk-forward validation

#### RandomForest Model
- **Type**: Ensemble Decision Trees
- **Features**: Same as XGBoost
- **Output**: Probability distribution [BUY, SELL, HOLD]
- **Purpose**: Diversification & vote confirmation

#### Ensemble Strategy

```python
final_probability = (
    xgb_probability * 0.6 + 
    rf_probability * 0.4
)

if final_probability['BUY'] > 0.60:
    signal = "BUY"
elif final_probability['SELL'] > 0.60:
    signal = "SELL"
else:
    signal = "HOLD"
```

### Phase 2: Reinforcement Learning (Future)

- **Algorithms**: PPO (Proximal Policy Optimization), SAC (Soft Actor-Critic)
- **Environment**: Custom Gymnasium trading environment
- **Reward Function**: Risk-adjusted returns (Sharpe ratio)
- **State Space**: Price action, indicators, position info
- **Action Space**: Buy, Sell, Hold, Close Position

### Phase 3: LLM Integration (Future)

- **Purpose**: News sentiment analysis, market explanation
- **Models**: Fine-tuned financial LLM
- **Output**: Sentiment score, trade rationale
- **Integration**: Combine with technical signals

---

## 🛡️ Risk Management

### Core Principles

1. **Capital Preservation**: Never risk more than 1% per trade
2. **Drawdown Control**: Maximum 5% daily loss limit
3. **Position Limits**: Maximum 3 concurrent trades
4. **Volatility Adjustment**: SL/TP based on ATR

### Risk Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Risk per Trade | 1% | Account equity percentage |
| Max Daily Loss | 5% | Trading halt threshold |
| Max Open Trades | 3 | Concurrent position limit |
| Min Reward:Risk | 1.5:1 | Minimum R:R ratio |
| Trailing Stop | Yes | Activate after 1R profit |

### Position Sizing Formula

```python
def calculate_lot_size(account_balance, risk_percent, stop_loss_pips):
    risk_amount = account_balance * (risk_percent / 100)
    pip_value = 10.0  # XAUUSD standard lot
    lot_size = risk_amount / (stop_loss_pips * pip_value)
    return round(lot_size, 2)
```

### Stop Loss & Take Profit

- **Stop Loss**: 2 × ATR(14) from entry
- **Take Profit**: 3 × ATR(14) from entry
- **Trailing Stop**: Activates after 1R profit, trails by 1.5 × ATR

---

## 🖥️ Dashboard

### Features

- **Real-time Price Display**: Current XAUUSD bid/ask
- **Market Trend**: Multi-timeframe trend visualization
- **AI Confidence**: Gauge showing BUY/SELL/HOLD probabilities
- **Open Trades**: Active positions with P&L
- **Risk Status**: Daily P&L, remaining risk budget
- **System Logs**: Live event feed
- **Performance Metrics**: Win rate, profit factor, Sharpe ratio

### Screenshots

*(To be added)*

### Running Dashboard

```bash
python Python/dashboard/gui.py
```

---

## 🗺️ Development Roadmap

### Phase 1: Foundation ✅ (Current)

- [x] Project architecture setup
- [x] Feature engineering pipeline
- [x] XGBoost model implementation
- [x] RandomForest model implementation
- [x] Risk manager module
- [x] SQLite database integration
- [x] Basic PyQt6 dashboard
- [ ] MQL5 EA communication layer
- [ ] End-to-end testing

### Phase 2: Reinforcement Learning (Q2 2025)

- [ ] Gymnasium trading environment
- [ ] PPO agent implementation
- [ ] SAC agent implementation
- [ ] Model ensemble with RL
- [ ] Backtesting framework

### Phase 3: LLM Integration (Q3 2025)

- [ ] News API integration
- [ ] Sentiment analysis model
- [ ] Trade report generation
- [ ] Market explanation module
- [ ] Hybrid signal generation

### Phase 4: Production Deployment (Q4 2025)

- [ ] Docker containerization
- [ ] Cloud deployment (AWS/GCP)
- [ ] Monitoring & alerting
- [ ] Performance optimization
- [ ] Multi-symbol support

---

## 🧪 Testing

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Coverage report
pytest --cov=Python tests/
```

### Test Coverage Goals

- **Minimum**: 80% code coverage
- **Critical Modules**: 95% (risk manager, execution)
- **Documentation**: 100% public APIs

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Code Standards

- **Python**: PEP 8 compliant
- **MQL5**: MQL5 style guide
- **Documentation**: Google docstring format
- **Testing**: pytest for all new features

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

**IMPORTANT RISK DISCLOSURE:**

1. **Trading Risk**: Trading foreign exchange and CFDs carries a high level of risk and may not be suitable for all investors. Leverage can work against you as well as for you.

2. **No Guarantee**: Past performance of this system is not indicative of future results. There is no guarantee that this system will produce profits or avoid losses.

3. **Educational Purpose**: This software is provided for educational and research purposes only. Use at your own risk.

4. **Not Financial Advice**: The information provided by this system does not constitute financial advice, investment recommendations, or solicitation to buy or sell any financial instruments.

5. **Test Thoroughly**: Always test any trading system in a demo environment before using real money.

6. **Only Risk What You Can Afford to Lose**: Never trade with money you cannot afford to lose.

**By using this software, you acknowledge that you have read, understood, and agree to this disclaimer.**

---

## 📞 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/MT5-AI-Trader-Pro/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/MT5-AI-Trader-Pro/discussions)
- **Email**: your.email@example.com

---

<div align="center">

**Built with ❤️ by the MT5-AI-Trader Team**

*Version 1.0.0 - January 2025*

</div>