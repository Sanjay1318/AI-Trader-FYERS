"""
Lag Features Module

Creates lag and rolling statistical features.
"""

from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = {
    "close",
    "volume",
}


def _validate_dataframe(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )


def add_lag_features(
    df: pd.DataFrame,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Add lag and rolling statistical features.
    """
    _validate_dataframe(df)

    if not inplace:
        df = df.copy()

    # ======================
    # Price Lags
    # ======================

    for lag in [1, 2, 3, 5, 10]:
        df[f"close_lag_{lag}"] = df["close"].shift(lag)

    # ======================
    # Volume Lags
    # ======================

    for lag in [1, 2, 3, 5]:
        df[f"volume_lag_{lag}"] = df["volume"].shift(lag)

    # ======================
    # Returns
    # ======================

    df["return_1"] = df["close"].pct_change(1)

    df["return_3"] = df["close"].pct_change(3)

    df["return_5"] = df["close"].pct_change(5)

    # ======================
    # Rolling Statistics
    # ======================

    df["rolling_mean_5"] = (
        df["close"]
        .rolling(5)
        .mean()
    )

    df["rolling_mean_10"] = (
        df["close"]
        .rolling(10)
        .mean()
    )

    df["rolling_std_5"] = (
        df["close"]
        .rolling(5)
        .std()
    )

    df["rolling_std_10"] = (
        df["close"]
        .rolling(10)
        .std()
    )

    df["rolling_min_10"] = (
        df["close"]
        .rolling(10)
        .min()
    )

    df["rolling_max_10"] = (
        df["close"]
        .rolling(10)
        .max()
    )

    return df