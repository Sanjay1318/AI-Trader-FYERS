"""
Technical Indicators Module
───────────────────────────
Only technical indicators live here.

Indicators (implemented):
  - EMA 20, EMA 50
  - RSI 14
  - ATR 14
  - ADX 14 (via pandas_ta)
  - MACD (12, 26, 9)
  - Derived relative-price features (return_1m, return_3m, return_5m,
    high_low_pct, close_open_pct, body_pct, rolling_volatility)

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

        REMOVED SMA20/SMA50: 100% redundant with EMA20/EMA50 (r=0.9996).

        NOTE: ADX uses pandas_ta.adx() which correctly implements
        Wilder's smoothing. The manual Wilder loop produced 100% NaN
        because the rolling-mean starter value (index 26) is after the
        Wilder loop start (index 14), propagating NaN everywhere.
        """
        df = df.copy()

        # ── Rename to avoid masking Python built-ins ─────────────────────────
        # "open" shadows built-in open(); "close"/"high"/"low" are safe but
        # renamed for consistency.
        open_price = df["open"]
        high_price = df["high"]
        low_price = df["low"]
        close_price = df["close"]
        volume = df["volume"]

        # ── Trend: EMAs ──────────────────────────────────────────────────────
        df["ema20"] = close_price.ewm(span=20, adjust=False).mean()
        df["ema50"] = close_price.ewm(span=50, adjust=False).mean()

        # ── Derived Relative-Price Features ──────────────────────────────────
        # Returns over multiple windows (percentage)
        df["return_1m"] = close_price.pct_change(periods=1) * 100.0
        df["return_3m"] = close_price.pct_change(periods=3) * 100.0
        df["return_5m"] = close_price.pct_change(periods=5) * 100.0

        # Candle geometry (relative, not absolute)
        df["high_low_pct"] = (high_price - low_price) / close_price.replace(0, np.nan) * 100.0
        df["close_open_pct"] = (close_price - open_price) / open_price.replace(0, np.nan) * 100.0
        candle_range = (high_price - low_price).replace(0, np.nan)
        df["body_pct"] = np.abs(close_price - open_price) / candle_range

        # Rolling volatility (20-period standard deviation of returns)
        df["rolling_volatility"] = df["return_1m"].rolling(window=20).std()

        # ── Momentum: RSI 14 ─────────────────────────────────────────────────
        delta = close_price.diff()
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
        prev_close = close_price.shift(1)
        tr = pd.concat([
            high_price - low_price,
            (high_price - prev_close).abs(),
            (low_price - prev_close).abs(),
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
        adx_result = ta.adx(high_price, low_price, close_price, length=14)
        if adx_result is not None and not adx_result.empty:
            df["adx"] = adx_result.iloc[:, 0]     # ADX value
            df["di_plus"] = adx_result.iloc[:, 1]  # +DI
            df["di_minus"] = adx_result.iloc[:, 2] # -DI
        else:
            df["adx"] = np.nan
            df["di_plus"] = np.nan
            df["di_minus"] = np.nan

        # ── MACD (12, 26, 9) ────────────────────────────────────────────────
        ema12 = close_price.ewm(span=12, adjust=False).mean()
        ema26 = close_price.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        df["macd"] = macd_line
        df["macd_signal"] = macd_signal
        df["macd_hist"] = macd_hist

        logger.info(
            f"TechnicalFeatures: added ema20, ema50, return_1m/3m/5m, "
            f"high_low_pct, close_open_pct, body_pct, rolling_volatility, "
            f"rsi, atr, adx, di_plus, di_minus, macd, macd_signal, macd_hist"
        )
        return df
