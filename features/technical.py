"""
Technical Indicators Module
───────────────────────────
Only technical indicators live here.

Indicators (implemented):
  - EMA 20, EMA 50
  - SMA 20, SMA 50
  - RSI 14
  - ATR 14
  - ADX 14 (via pandas_ta)
  - MACD (12, 26, 9)

Left for later milestones:
  - Ichimoku, SuperTrend, Stochastic, CCI, Bollinger Bands
"""

import numpy as np
import pandas as pd
import pandas_ta as ta

from features.feature_base import BaseFeatureModule
from utils.logger import get_logger

logger = get_logger("technical")


class TechnicalFeatures(BaseFeatureModule):
    """Computes all technical indicators for the feature pipeline."""

    def required_columns(self) -> list:
        return ["open", "high", "low", "close", "volume"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute technical indicators on OHLCV DataFrame.
        Returns augmented DataFrame with indicator columns added.

        NOTE: ADX uses pandas_ta.adx() which correctly implements
        Wilder's smoothing. The manual Wilder loop produced 100% NaN
        because the rolling-mean starter value (index 26) is after the
        Wilder loop start (index 14), propagating NaN everywhere.
        """
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # ── Trend: EMAs ──────────────────────────────────────────────────────
        df["ema20"] = close.ewm(span=20, adjust=False).mean()
        df["ema50"] = close.ewm(span=50, adjust=False).mean()

        # ── Trend: SMAs ──────────────────────────────────────────────────────
        df["sma20"] = close.rolling(window=20).mean()
        df["sma50"] = close.rolling(window=50).mean()

        # ── Momentum: RSI 14 ─────────────────────────────────────────────────
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()

        # Wilder's smoothing: first value is SMA, subsequent use exponential decay
        for i in range(14, len(avg_gain)):
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * 13 + gain.iloc[i]) / 14
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * 13 + loss.iloc[i]) / 14

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # ── Volatility: ATR 14 ──────────────────────────────────────────────
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr = tr.rolling(window=14, min_periods=14).mean()
        # Wilder's smoothing for ATR — same pattern, but ATR's first valid
        # rolling value is at index 13, loop at 14 works correctly here
        for i in range(14, len(atr)):
            atr.iloc[i] = (atr.iloc[i - 1] * 13 + tr.iloc[i]) / 14
        df["atr"] = atr

        # ── Trend Strength: ADX 14 (via pandas_ta) ───────────────────────────
        # CRITICAL: pandas_ta.adx() correctly handles Wilder's smoothing.
        # The manual loop was broken because dx.rolling(14).mean() first
        # valid value is at index 26, but the Wilder loop started at index
        # 14, propagating NaN throughout.
        adx_result = ta.adx(high, low, close, length=14)
        if adx_result is not None and not adx_result.empty:
            df["adx"] = adx_result.iloc[:, 0]     # ADX value
            df["di_plus"] = adx_result.iloc[:, 1]  # +DI
            df["di_minus"] = adx_result.iloc[:, 2] # -DI
        else:
            df["adx"] = np.nan
            df["di_plus"] = np.nan
            df["di_minus"] = np.nan

        # ── MACD (12, 26, 9) ────────────────────────────────────────────────
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        df["macd"] = macd_line
        df["macd_signal"] = macd_signal
        df["macd_hist"] = macd_hist

        logger.info(
            f"TechnicalFeatures: added ema20, ema50, sma20, sma50, rsi, atr, adx, "
            f"di_plus, di_minus, macd, macd_signal, macd_hist"
        )
        return df
