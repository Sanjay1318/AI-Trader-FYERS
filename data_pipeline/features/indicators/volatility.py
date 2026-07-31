"""
Volatility Indicators Module

Computes volatility-based technical indicators for OHLCV data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
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


def calculate_true_range(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series
) -> pd.Series:
    """
    Calculate True Range.
    """
    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Average True Range.
    """
    tr = calculate_true_range(high, low, close)

    atr = tr.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    return atr


def calculate_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
):
    """
    Calculate Bollinger Bands.
    """
    middle = close.rolling(
        window=period,
        min_periods=period
    ).mean()

    std = close.rolling(
        window=period,
        min_periods=period
    ).std()

    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)

    return upper, middle, lower


def calculate_historical_volatility(
    close: pd.Series,
    period: int = 20
) -> pd.Series:
    """
    Historical Volatility.
    """
    log_returns = np.log(close / close.shift(1))

    volatility = (
        log_returns
        .rolling(period)
        .std()
        * np.sqrt(period)
    )

    return volatility


def add_volatility_features(
    df: pd.DataFrame,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Add volatility features.
    """
    _validate_dataframe(df)

    if not inplace:
        df = df.copy()

    df["true_range"] = calculate_true_range(
        df["high"],
        df["low"],
        df["close"],
    )

    df["atr_14"] = calculate_atr(
        df["high"],
        df["low"],
        df["close"],
    )

    (
        df["bb_upper"],
        df["bb_middle"],
        df["bb_lower"],
    ) = calculate_bollinger_bands(
        df["close"]
    )

    denominator = (
        df["bb_upper"] - df["bb_lower"]
    ).replace(0, np.nan)

    df["bb_width"] = (
        denominator / df["bb_middle"]
    )

    df["bb_percent_b"] = (
        (df["close"] - df["bb_lower"])
        / denominator
    )

    df["hist_volatility_20"] = (
        calculate_historical_volatility(
            df["close"]
        )
    )

    return df