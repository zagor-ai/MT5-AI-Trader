"""MT5 connection and terminal diagnostics boundary.

Research-only: this module intentionally exposes no trading-order API.
"""

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    mt5 = None

from .utils import safe_float


def mt5_error_text() -> str:
    if mt5 is None:
        return "MetaTrader5 package unavailable"
    try:
        return str(mt5.last_error())
    except Exception:
        return "Unknown MT5 error"


class MT5Connector:
    def __init__(self):
        self.connected = False

    def initialize(self):
        if mt5 is None:
            raise RuntimeError(
                "MetaTrader5 package is not installed. "
                "Install with: python -m pip install MetaTrader5"
            )
        if self.connected:
            return
        if not mt5.initialize():
            self.connected = False
            raise RuntimeError(
                f"mt5.initialize() failed. Last error: {mt5_error_text()}"
            )
        self.connected = True

    def shutdown(self):
        if mt5 is not None:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self.connected = False

    def terminal_info(self):
        self.initialize()
        info = mt5.terminal_info()
        if info is None:
            raise RuntimeError(
                f"terminal_info() failed. Last error: {mt5_error_text()}"
            )
        return info

    def account_info(self):
        self.initialize()
        return mt5.account_info()

    def ensure_symbol(self, symbol: str):
        self.initialize()
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(
                f"Symbol '{symbol}' is not available. Last error: {mt5_error_text()}"
            )
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Cannot select {symbol}. Last error: {mt5_error_text()}"
            )
        return info

    def tick(self, symbol: str):
        self.ensure_symbol(symbol)
        return mt5.symbol_info_tick(symbol)

    def diagnostics(self, symbol: str) -> dict:
        terminal = self.terminal_info()
        account = self.account_info()
        symbol_info = self.ensure_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        return {
            "terminal": terminal,
            "account": account,
            "symbol": symbol_info,
            "tick": tick,
            "connected": self.connected,
            "bid": safe_float(getattr(tick, "bid", 0.0)),
            "ask": safe_float(getattr(tick, "ask", 0.0)),
        }
