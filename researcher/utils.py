"""Shared, dependency-light helpers."""

import math
from datetime import datetime


def finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def safe_float(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def now_text() -> str:
    return datetime.now().strftime("%H:%M:%S")
