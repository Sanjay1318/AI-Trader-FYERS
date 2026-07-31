"""
Time Features Module

Creates calendar and cyclical time-based features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "date",
}


def _validate_dataframe(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )


def add_time_features(
    df: pd.DataFrame,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Add time-based features.
    """
    _validate_dataframe(df)

    if not inplace:
        df = df.copy()

    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])

    # Calendar features

    df["year"] = df["date"].dt.year

    df["month"] = df["date"].dt.month

    df["quarter"] = df["date"].dt.quarter

    df["week"] = df["date"].dt.isocalendar().week.astype(int)

    df["day"] = df["date"].dt.day

    df["day_of_week"] = df["date"].dt.dayofweek

    df["day_of_year"] = df["date"].dt.dayofyear

    df["is_month_start"] = (
        df["date"].dt.is_month_start
    ).astype(np.int8)

    df["is_month_end"] = (
        df["date"].dt.is_month_end
    ).astype(np.int8)

    # Cyclical encoding

    df["month_sin"] = np.sin(
        2 * np.pi * df["month"] / 12
    )

    df["month_cos"] = np.cos(
        2 * np.pi * df["month"] / 12
    )

    df["dayofweek_sin"] = np.sin(
        2 * np.pi * df["day_of_week"] / 7
    )

    df["dayofweek_cos"] = np.cos(
        2 * np.pi * df["day_of_week"] / 7
    )

    return df