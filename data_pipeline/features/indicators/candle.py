"""
Candlestick Features Module

Computes candlestick-based features for OHLCV data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
}


def _validate_dataframe(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )


def add_candlestick_features(
    df: pd.DataFrame,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Add candlestick-based features.
    """
    _validate_dataframe(df)

    if not inplace:
        df = df.copy()

    # Basic measurements

    body = df["close"] - df["open"]

    abs_body = body.abs()

    candle_range = (
        df["high"] - df["low"]
    ).replace(0, np.nan)

    upper_wick = (
        df["high"]
        - np.maximum(df["open"], df["close"])
    )

    lower_wick = (
        np.minimum(df["open"], df["close"])
        - df["low"]
    )

    df["body_size"] = abs_body

    df["upper_wick"] = upper_wick

    df["lower_wick"] = lower_wick

    df["candle_range"] = candle_range

    df["body_percent"] = (
        abs_body / candle_range
    )

    # Candle direction

    df["bullish_candle"] = (
        df["close"] > df["open"]
    ).astype(np.int8)

    df["bearish_candle"] = (
        df["close"] < df["open"]
    ).astype(np.int8)

    # Doji

    df["doji"] = (
        df["body_percent"] <= 0.10
    ).astype(np.int8)

    # Hammer

    df["hammer"] = (
        (lower_wick >= abs_body * 2)
        &
        (upper_wick <= abs_body)
    ).astype(np.int8)

    # Shooting Star

    df["shooting_star"] = (
        (upper_wick >= abs_body * 2)
        &
        (lower_wick <= abs_body)
    ).astype(np.int8)

    # Bullish Engulfing

    previous_open = df["open"].shift(1)
    previous_close = df["close"].shift(1)

    df["bullish_engulfing"] = (
        (previous_close < previous_open)
        &
        (df["close"] > df["open"])
        &
        (df["open"] < previous_close)
        &
        (df["close"] > previous_open)
    ).astype(np.int8)

    # Bearish Engulfing

    df["bearish_engulfing"] = (
        (previous_close > previous_open)
        &
        (df["close"] < df["open"])
        &
        (df["open"] > previous_close)
        &
        (df["close"] < previous_open)
    ).astype(np.int8)

    return df