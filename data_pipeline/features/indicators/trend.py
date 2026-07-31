"""
trend.py

Trend indicator calculations.
"""

import pandas as pd


# ==========================================================
# Moving Averages
# ==========================================================

def sma(df: pd.DataFrame, period: int):
    """
    Simple Moving Average
    """
    return df["close"].rolling(period).mean()


def ema(df: pd.DataFrame, period: int):
    """
    Exponential Moving Average
    """
    return df["close"].ewm(
        span=period,
        adjust=False
    ).mean()


def wma(df: pd.DataFrame, period: int):
    """
    Weighted Moving Average
    """

    weights = list(range(1, period + 1))

    return df["close"].rolling(period).apply(
        lambda prices: (prices * weights).sum() / sum(weights),
        raw=True
    )


# ==========================================================
# Trend Builder
# ==========================================================

def add_trend_features(df: pd.DataFrame):

    sma_periods = [
        5,
        10,
        20,
        50,
        100,
        200
    ]

    ema_periods = [
        5,
        10,
        20,
        50,
        100,
        200
    ]

    wma_periods = [
        20,
        50
    ]

    for p in sma_periods:
        df[f"sma_{p}"] = sma(df, p)

    for p in ema_periods:
        df[f"ema_{p}"] = ema(df, p)

    for p in wma_periods:
        df[f"wma_{p}"] = wma(df, p)

    return df