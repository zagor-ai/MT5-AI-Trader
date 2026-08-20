# -*- coding: utf-8 -*-
"""Compatibility launcher for XAU Strategy Researcher Pro v2.1.1.

The application logic is now modular. New code belongs in ``gui/``,
``core/``, ``researcher/`` and ``services/``. This file is intentionally tiny
so older BAT files and shortcuts can continue launching the application.

Research-only: MetaTrader 5 is never used to submit, modify, or close orders.
"""
from app import run_app


if __name__ == "__main__":
    run_app()
