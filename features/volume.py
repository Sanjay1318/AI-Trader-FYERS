"""
Volume Features Module
──────────────────────
Only volume-based features live here.

Features (implemented):
  - VWAP (Volume-Weighted Average Price)
  - Volume SMA20 (rolling average volume)
  - Relative Volume (volume / volume_sma20)
  - OBV (On-Balance Volume)

Left for later milestones:
  - CMF, MFI, Volume Oscillator, Volume Spike Detection
"""

import numpy as np
import pandas as pd

from features.feature_base import BaseFeatureModule
from utils.logger import get_logger

logger = get_logger("volume")


class VolumeFeatures(BaseFeatureModule):
    """Computes all volume-derived features."""

    def required_columns(self) -> list:
        return ["open", "high", "low", "close", "volume"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute volume features. Returns augmented DataFrame.
        All calculations are per-symbol (assumes single symbol in input).
        """
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # ── VWAP (Volume-Weighted Average Price) ─────────────────────────────
        # VWAP = cumulative(typical_price * volume) / cumulative(volume)
        typical_price = (high + low + close) / 3.0
        cum_tp_vol = (typical_price * volume).cumsum()
        cum_vol = volume.cumsum().replace(0, np.nan)
        df["vwap"] = cum_tp_vol / cum_vol

        # Distance from VWAP (as % of price)
        df["vwap_dist_pct"] = (close - df["vwap"]) / df["vwap"].replace(0, np.nan) * 100.0

        # ── Volume SMA20 ─────────────────────────────────────────────────────
        df["volume_sma20"] = volume.rolling(window=20).mean()

        # ── Relative Volume ──────────────────────────────────────────────────
        df["relative_volume"] = volume / df["volume_sma20"].replace(0, np.nan)

        # ── OBV (On-Balance Volume) ──────────────────────────────────────────
        # OBV adds volume when close > prev_close, subtracts when close < prev_close
        close_diff = close.diff()
        obv = (np.sign(close_diff) * volume).fillna(0).cumsum()
        # Normalize OBV to make it scale-independent
        obv_ma = obv.rolling(window=20).mean().replace(0, np.nan)
        df["obv"] = obv
        df["obv_normalized"] = (obv - obv_ma) / obv.rolling(window=20).std().replace(0, np.nan)

        logger.info(
            f"VolumeFeatures: added vwap, vwap_dist_pct, volume_sma20, "
            f"relative_volume, obv, obv_normalized"
        )
        return df

