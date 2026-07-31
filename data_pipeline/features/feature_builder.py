"""
Feature Builder

Runs all feature engineering modules on cleaned market data.
"""

from __future__ import annotations

import pandas as pd

from data_pipeline.features.indicators.trend import add_trend_features
from data_pipeline.features.indicators.momentum import add_momentum_features
from data_pipeline.features.indicators.volatility import add_volatility_features
from data_pipeline.features.indicators.volume import add_volume_features
from data_pipeline.features.indicators.candle import add_candlestick_features
from data_pipeline.features.indicators.time_features import add_time_features
from data_pipeline.features.indicators.lag_features import add_lag_features


def build_features(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Apply all feature engineering modules.
    """

    df = add_trend_features(df)
    df = add_momentum_features(df)
    df = add_volatility_features(df)
    df = add_volume_features(df)
    df = add_candlestick_features(df)
    df = add_time_features(df)
    df = add_lag_features(df)

    return df