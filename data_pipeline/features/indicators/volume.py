"""
Volume Indicators Module

Computes volume-based technical indicators for OHLCV data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "high",
    "low",
    "close",
    "volume",
}


def _validate_dataframe(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )


def calculate_obv(
    close: pd.Series,
    volume: pd.Series
) -> pd.Series:
    """
    On Balance Volume.
    """
    direction = np.sign(close.diff()).fillna(0)

    obv = (direction * volume).cumsum()

    return obv


def calculate_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series
) -> pd.Series:
    """
    Volume Weighted Average Price.
    """
    typical_price = (high + low + close) / 3

    cumulative_tp_volume = (typical_price * volume).cumsum()
    cumulative_volume = volume.cumsum()

    return cumulative_tp_volume / cumulative_volume


def calculate_adl(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series
) -> pd.Series:
    """
    Accumulation Distribution Line.
    """
    denominator = (high - low).replace(0, np.nan)

    money_flow_multiplier = (
        ((close - low) - (high - close))
        / denominator
    ).fillna(0)

    money_flow_volume = (
        money_flow_multiplier * volume
    )

    return money_flow_volume.cumsum()


def calculate_cmf(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20
) -> pd.Series:
    """
    Chaikin Money Flow.
    """
    denominator = (high - low).replace(0, np.nan)

    multiplier = (
        ((close - low) - (high - close))
        / denominator
    ).fillna(0)

    mfv = multiplier * volume

    cmf = (
        mfv.rolling(period).sum()
        /
        volume.rolling(period).sum()
    )

    return cmf


def add_volume_features(
    df: pd.DataFrame,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Add volume features.
    """
    _validate_dataframe(df)

    if not inplace:
        df = df.copy()

    df["obv"] = calculate_obv(
        df["close"],
        df["volume"]
    )

    df["vwap"] = calculate_vwap(
        df["high"],
        df["low"],
        df["close"],
        df["volume"]
    )

    df["volume_sma_20"] = (
        df["volume"]
        .rolling(20)
        .mean()
    )

    df["volume_ratio"] = (
        df["volume"]
        /
        df["volume_sma_20"]
    )

    df["volume_change_pct"] = (
        df["volume"]
        .pct_change()
        * 100
    )

    df["relative_volume"] = (
        df["volume"]
        /
        df["volume_sma_20"]
    )

    df["adl"] = calculate_adl(
        df["high"],
        df["low"],
        df["close"],
        df["volume"]
    )

    df["cmf_20"] = calculate_cmf(
        df["high"],
        df["low"],
        df["close"],
        df["volume"]
    )

    return df