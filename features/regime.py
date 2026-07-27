"""
Market Regime Classification Module
─────────────────────────────────────
Classifies the current market environment into regimes.

Regimes:
  - trending_bull
  - trending_bear
  - sideways
  - high_volatility
  - low_volatility
  - choppy
  - unknown
"""

import numpy as np
import pandas as pd

from features.feature_base import BaseFeatureModule
from utils.logger import get_logger

logger = get_logger("regime")


class RegimeFeatures(BaseFeatureModule):
    """Detects and classifies market regime from OHLC data."""

    def required_columns(self) -> list:
        return ["open", "high", "low", "close"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect market regime. Returns augmented DataFrame with regime column."""
        if df.empty:
            df = df.copy()
            df["regime"] = "unknown"
            df["regime_value"] = -1
            return df

        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # ── EMAs for trend detection ───────────────────────────────────────
        ema20_s = close.ewm(span=20, adjust=False).mean()
        ema50_s = close.ewm(span=50, adjust=False).mean()

        # ── ATR for volatility ──────────────────────────────────────────────
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr_s = tr.rolling(window=14, min_periods=1).mean()
        atr_pct_s = atr_s / close.replace(0, np.nan)

        # Trend strength
        ema_diff = (ema20_s - ema50_s) / ema50_s.replace(0, np.nan)
        ema_slope = ema20_s.diff(5) / ema20_s.shift(5).replace(0, np.nan)

        # Volatility percentiles (full history for thresholds)
        atr_history = atr_pct_s.dropna()
        if len(atr_history) > 10:
            vol_high_thresh = np.percentile(atr_history, 75)
            vol_low_thresh = np.percentile(atr_history, 25)
        else:
            vol_high_thresh = atr_pct_s.quantile(0.75)
            vol_low_thresh = atr_pct_s.quantile(0.25)

        # Price range compression (recent 20 bars)
        recent_high = high.tail(20).max()
        recent_low = low.tail(20).min()
        range_pct = (recent_high - recent_low) / close.iloc[-1] if len(close) > 0 else 0

        # ADX-like directional strength
        direction = np.sign(close.diff())
        adx_like = direction.rolling(window=14).mean().abs()

        # ── Classify each row ──────────────────────────────────────────────
        regimes = []
        for i in range(len(df)):
            if pd.isna(ema_diff.iloc[i]) or pd.isna(atr_pct_s.iloc[i]):
                regimes.append("unknown")
                continue

            atr_val = atr_pct_s.iloc[i]
            ed = ema_diff.iloc[i]
            es = ema_slope.iloc[i]
            adx = adx_like.iloc[i]

            is_high_vol = atr_val > vol_high_thresh if not pd.isna(atr_val) else False
            is_low_vol = atr_val < vol_low_thresh if not pd.isna(atr_val) else False

            if is_high_vol:
                regimes.append("high_volatility")
            elif is_low_vol:
                regimes.append("low_volatility")
            elif ed > 0.002 and es > 0 and adx > 0.3:
                regimes.append("trending_bull")
            elif ed < -0.002 and es < 0 and adx > 0.3:
                regimes.append("trending_bear")
            elif range_pct < 0.01 or adx < 0.15:
                regimes.append("sideways")
            elif ed > 0:
                regimes.append("trending_bull")
            elif ed < 0:
                regimes.append("trending_bear")
            else:
                regimes.append("unknown")

        df["regime"] = regimes
        df["regime_value"] = pd.factorize(np.array(regimes))[0]

        logger.info(f"RegimeFeatures: added regime column")
        return df
