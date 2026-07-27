"""
Volatility Features Module
───────────────────────────
Everything related to volatility.

Features:
  - ATR (Average True Range)
  - Historical Volatility (annualised std of log returns)
  - Rolling Std Dev of returns (20-period, 60-period)
  - Realized Volatility (sum of squared 1-min returns over 20 periods)
  - Parkinson Volatility (high-low based estimator)
  - Range Expansion (current range vs average range)
"""

import numpy as np
import pandas as pd

from features.feature_base import BaseFeatureModule
from utils.logger import get_logger

logger = get_logger("volatility")


class VolatilityFeatures(BaseFeatureModule):
    """Computes volatility-related features from OHLC data."""

    def required_columns(self) -> list:
        return ["open", "high", "low", "close"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volatility features. Returns augmented DataFrame."""
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        prev_close = close.shift(1)

        # ── ATR ─────────────────────────────────────────────────────────────
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14, min_periods=1).mean()
        df["atr_pct"] = df["atr"] / close.replace(0, np.nan)

        # ── Historical Volatility (annualised, 20-period) ───────────────────
        log_returns = np.log(close / prev_close)
        hv_20 = log_returns.rolling(window=20, min_periods=1).std()
        df["hv_20"] = hv_20 * np.sqrt(252 * 375)  # annualise (252 days x 375 min)
        hv_60 = log_returns.rolling(window=60, min_periods=1).std()
        df["hv_60"] = hv_60 * np.sqrt(252 * 375)

        # ── Rolling Std Dev of returns ──────────────────────────────────────
        df["volatility_20"] = log_returns.rolling(window=20, min_periods=1).std()
        df["volatility_60"] = log_returns.rolling(window=60, min_periods=1).std()
        df["vol_regime"] = (df["volatility_20"] / df["volatility_60"].replace(0, np.nan))

        # ── Realized Volatility ─────────────────────────────────────────────
        squared_returns = log_returns ** 2
        df["rv_20"] = squared_returns.rolling(window=20, min_periods=1).sum()
        df["rv_60"] = squared_returns.rolling(window=60, min_periods=1).sum()

        # ── Parkinson Volatility ────────────────────────────────────────────
        parkinson = (np.log(high / low) ** 2) / (4 * np.log(2))
        df["parkinson_vol"] = parkinson.rolling(window=20, min_periods=1).mean()
        df["parkinson_vol"] = np.sqrt(df["parkinson_vol"])

        # ── Range Expansion ─────────────────────────────────────────────────
        candle_range = high - low
        df["range_pct"] = candle_range / close.replace(0, np.nan)
        avg_range = candle_range.rolling(window=20, min_periods=1).mean()
        df["range_expansion"] = candle_range / avg_range.replace(0, np.nan)

        logger.info(f"VolatilityFeatures: added atr, hv_20, hv_60, volatility_20/60, rv_20/60, parkinson_vol, range_expansion")
        return df

