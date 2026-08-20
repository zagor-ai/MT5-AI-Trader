"""Chronological train/test splitting for strategy research."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class SplitResult:
    train: pd.DataFrame
    test: pd.DataFrame
    split_index: int
    train_ratio: float

def chronological_split(data: pd.DataFrame, train_ratio: float = 0.70) -> SplitResult:
    if not 0.5 <= train_ratio < 1.0:
        raise ValueError("train_ratio must be >= 0.50 and < 1.0")
    if len(data) < 100:
        raise ValueError("At least 100 bars are required for train/test validation")
    split = int(len(data) * train_ratio)
    if split <= 0 or split >= len(data):
        raise ValueError("Invalid split point")
    return SplitResult(data.iloc[:split].copy(), data.iloc[split:].copy(), split, train_ratio)
