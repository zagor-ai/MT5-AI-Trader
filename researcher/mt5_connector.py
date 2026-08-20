"""Legacy compatibility wrapper for the canonical read-only MT5 connector.

Use ``services.mt5_connector.MT5Connector`` for new code. This module is
kept temporarily so existing imports do not break during the modular
migration. It exposes diagnostics and historical-data access only; it has
no order/trading API.
"""
from services.mt5_connector import MT5Connector, MT5Diagnostics

__all__ = ["MT5Connector", "MT5Diagnostics"]
