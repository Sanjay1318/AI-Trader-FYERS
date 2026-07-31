"""
Momentum Indicators Module

This module computes momentum-based technical indicators for OHLCV market data.

Expected input columns:
    - open
    - high
    - low
    - close
    - volume

Generated indicators:
    - RSI (14)
    - Stochastic %K (14)
    - Stochastic %D (3)
    - Rate of Change (10)
    - Commodity Channel Index (20)
    - Williams %R (14)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def _validate_dataframe(df: pd.DataFrame) -> None:
    """
    Validate that the input DataFrame contains all required OHLCV columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input market data.

    Raises
    ------
    ValueError
        If any required column is missing.
    """
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

def calculate_rsi(
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate the Relative Strength Index (RSI).
    """
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    # Handle edge cases
    rsi = rsi.where(avg_loss != 0, 100)
    rsi = rsi.where(avg_gain != 0, 0)

    return rsi

def calculate_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3
) -> tuple[pd.Series, pd.Series]:
    """
    Calculate the Stochastic Oscillator (%K and %D).

    Parameters
    ----------
    high : pd.Series
        High prices.
    low : pd.Series
        Low prices.
    close : pd.Series
        Closing prices.
    k_period : int, default=14
        Lookback period for %K.
    d_period : int, default=3
        Moving average period for %D.

    Returns
    -------
    tuple[pd.Series, pd.Series]
        (%K, %D)
    """
    lowest_low = low.rolling(
        window=k_period,
        min_periods=k_period
    ).min()

    highest_high = high.rolling(
        window=k_period,
        min_periods=k_period
    ).max()

    denominator = (highest_high - lowest_low).replace(0, np.nan)

    percent_k = (
        (close - lowest_low) / denominator
    ) * 100

    percent_d = percent_k.rolling(
        window=d_period,
        min_periods=d_period
    ).mean()

    return percent_k, percent_d

def calculate_roc(
    close: pd.Series,
    period: int = 10
) -> pd.Series:
    """
    Calculate the Rate of Change (ROC).

    Parameters
    ----------
    close : pd.Series
        Closing prices.
    period : int, default=10
        Lookback period.

    Returns
    -------
    pd.Series
        Percentage Rate of Change.
    """
    return ((close / close.shift(period)) - 1.0) * 100.0


def calculate_cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20
) -> pd.Series:
    """
    Calculate the Commodity Channel Index (CCI).

    Parameters
    ----------
    high : pd.Series
    low : pd.Series
    close : pd.Series
    period : int, default=20

    Returns
    -------
    pd.Series
        CCI values.
    """
    typical_price = (high + low + close) / 3.0

    sma = typical_price.rolling(
        window=period,
        min_periods=period
    ).mean()

    mean_deviation = typical_price.rolling(
        window=period,
        min_periods=period
    ).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))),
        raw=True
    )

    denominator = (0.015 * mean_deviation).replace(0, np.nan)

    cci = (typical_price - sma) / denominator

    return cci


def calculate_williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate Williams %R.

    Parameters
    ----------
    high : pd.Series
    low : pd.Series
    close : pd.Series
    period : int, default=14

    Returns
    -------
    pd.Series
        Williams %R values.
    """
    highest_high = high.rolling(
        window=period,
        min_periods=period
    ).max()

    lowest_low = low.rolling(
        window=period,
        min_periods=period
    ).min()

    denominator = (highest_high - lowest_low).replace(0, np.nan)

    williams_r = (
        (highest_high - close)
        / denominator
    ) * -100

    return williams_r

def add_momentum_features(
    df: pd.DataFrame,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Add momentum-based technical indicators.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame.
    inplace : bool, default=False
        If True, modify the original DataFrame.

    Returns
    -------
    pd.DataFrame
        DataFrame containing momentum features.
    """
    _validate_dataframe(df)

    if not inplace:
        df = df.copy()

    # ======================
    # Momentum Indicators
    # ======================

    df["rsi_14"] = calculate_rsi(df["close"])

    df["stoch_k_14"], df["stoch_d_3"] = calculate_stochastic(
        df["high"],
        df["low"],
        df["close"]
    )

    df["roc_10"] = calculate_roc(df["close"])

    df["cci_20"] = calculate_cci(
        df["high"],
        df["low"],
        df["close"]
    )

    df["williams_r_14"] = calculate_williams_r(
        df["high"],
        df["low"],
        df["close"]
    )

    # ======================
    # ML Features
    # ======================

    df["rsi_change"] = df["rsi_14"].diff()

    df["rsi_overbought"] = (df["rsi_14"] >= 70).astype(np.int8)
    df["rsi_oversold"] = (df["rsi_14"] <= 30).astype(np.int8)

    df["roc_positive"] = (df["roc_10"] > 0).astype(np.int8)

    df["stoch_crossover"] = (
        (df["stoch_k_14"] > df["stoch_d_3"]) &
        (df["stoch_k_14"].shift(1) <= df["stoch_d_3"].shift(1))
    ).astype(np.int8)

    return df