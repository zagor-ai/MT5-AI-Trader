"""Read-only MetaTrader 5 connector for the Researcher.

This module deliberately contains no order/trading methods.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
import sys

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


@dataclass
class MT5Diagnostics:
    connected: bool = False
    terminal: str = ""
    build: str = ""
    account: str = ""
    server: str = ""
    symbol_available: bool = False
    symbol: str = "XAUUSD"
    digits: str = ""
    point: str = ""
    bid: str = ""
    ask: str = ""
    error: str = ""


class MT5Connector:
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.last = MT5Diagnostics(symbol=symbol)

    def diagnostics(self) -> MT5Diagnostics:
        d = MT5Diagnostics(symbol=self.symbol)
        if mt5 is None:
            d.error = "MetaTrader5 package is not installed."
            self.last = d
            return d
        if not mt5.initialize():
            d.error = f"initialize() failed: {mt5.last_error()}"
            self.last = d
            return d
        d.connected = True
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        info = mt5.symbol_info(self.symbol)
        tick = mt5.symbol_info_tick(self.symbol)
        if terminal:
            d.terminal = getattr(terminal, "name", "MetaTrader 5")
            d.build = str(getattr(terminal, "build", ""))
        if account:
            d.account = str(getattr(account, "login", ""))
            d.server = str(getattr(account, "server", ""))
        if info:
            d.symbol_available = bool(getattr(info, "visible", False) or getattr(info, "select", False))
            d.digits = str(getattr(info, "digits", ""))
            d.point = str(getattr(info, "point", ""))
        if tick:
            d.bid = f"{float(tick.bid):.3f}"
            d.ask = f"{float(tick.ask):.3f}"
        else:
            d.error = f"No tick for {self.symbol}: {mt5.last_error()}"
        self.last = d
        return d

    def load_rates(self, timeframe_name: str, bars: int):
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed.")
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        mapping = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
        }
        if timeframe_name not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe_name}")
        bars = max(1, min(int(bars), 500000))
        rates = mt5.copy_rates_from_pos(self.symbol, mapping[timeframe_name], 0, bars)
        if rates is None:
            raise RuntimeError(f"copy_rates_from_pos failed: {mt5.last_error()}")
        return rates
