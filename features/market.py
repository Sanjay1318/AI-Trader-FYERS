"""
Market Context Features Module
───────────────────────────────
Market context and session-based features.

Features:
  - Session (pre_open, opening, early, mid, late, closing, outside_market)
  - Gap Up / Gap Down detection
  - Opening Range (first 15-min high/low)
  - Previous Day High / Low / Close
  - Distance from VWAP (if available)
  - Distance from Day High / Low
  - Time since session start
  - Session progress (0.0–1.0)
  - Day range as percentage

Timezone handling:
  Database timestamps are TIMESTAMPTZ (UTC). All Indian-market session
  calculations must explicitly convert to Asia/Kolkata before classifying.
  The raw UTC timestamps are NOT modified.
"""

import numpy as np
import pandas as pd

from features.feature_base import BaseFeatureModule
from utils.logger import get_logger

logger = get_logger("market")

# IST market-time constants (minutes since midnight IST)
IST_PRE_OPEN_START = 540    # 09:00
IST_OPEN_START     = 555    # 09:15
IST_OPEN_END       = 570    # 09:30
IST_EARLY_END      = 660    # 11:00
IST_MID_END        = 810    # 13:30
IST_LATE_END       = 900    # 15:00
IST_CLOSE_END      = 930    # 15:30

SESSION_START = IST_OPEN_START
SESSION_END = IST_CLOSE_END

SESSION_LENGTH = SESSION_END - SESSION_START  # 375 minutes


class MarketFeatures(BaseFeatureModule):
    """Computes market context features from OHLCV data."""

    def required_columns(self) -> list:
        return ["open", "high", "low", "close", "volume"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute market context features. Returns augmented DataFrame."""
        df = df.copy()

        has_timestamp = "timestamp" in df.columns
        if has_timestamp:
            ts = pd.to_datetime(df["timestamp"])

            # ── CRITICAL: Convert to Asia/Kolkata for all Indian market time calculations ──
            # DB timestamps are TIMESTAMPTZ (UTC). Session classification MUST use IST.
            ist = ts.dt.tz_convert("Asia/Kolkata")
            minutes = ist.dt.hour * 60 + ist.dt.minute

            df["minutes_since_open"] = (minutes - SESSION_START).clip(lower=0)
            df["session_progress"] = (df["minutes_since_open"] / SESSION_LENGTH).clip(0, 1)
            df["day_of_week"] = ist.dt.dayofweek

            # ── Session Label (IST market-time buckets) ─────────────────
            #   pre_open:      09:00 <= time < 09:15  (540-554)
            #   opening:       09:15 <= time < 09:30  (555-569)
            #   early:         09:30 <= time < 11:00  (570-659)
            #   mid:           11:00 <= time < 13:30  (660-809)
            #   late:          13:30 <= time < 15:00  (810-899)
            #   closing:       15:00 <= time <= 15:30 (900-930)
            #   outside_market: everything else
            conditions = [
                minutes < IST_OPEN_START,           # before 09:15 IST
                minutes < IST_OPEN_END,             # 09:15-09:29 IST
                minutes < IST_EARLY_END,            # 09:30-10:59 IST
                minutes < IST_MID_END,              # 11:00-13:29 IST
                minutes < IST_LATE_END,             # 13:30-14:59 IST
                minutes <= IST_CLOSE_END,           # 15:00-15:30 IST
            ]
            labels = ["pre_open", "opening", "early", "mid", "late", "closing"]
            df["session"] = np.select(conditions, labels, default="outside_market")
            df["is_first_hour"] = (df["minutes_since_open"] <= 60).astype(int)
            df["is_last_hour"] = (df["minutes_since_open"] >= (SESSION_LENGTH - 60)).astype(int)

            # ── Gap detection (use IST date for proper trading-day grouping) ─
            df["date"] = ist.dt.date
            daily_open = df.groupby("date")["open"].transform("first")

            # FIX: Previous-day close computed from DAILY aggregation, not group-shift.
            # Old bug: groupby("date")["close"].shift(1) shifts within the same date group,
            # yielding NaN for every first bar of each day → gap_pct was 100% NaN.
            daily_last_close = df.groupby("date")["close"].last()
            prev_day_close = daily_last_close.shift(1)  # cross-day shift
            df["_prev_day_close"] = df["date"].map(prev_day_close)

            is_first_bar = df.groupby("date").cumcount() == 0
            gap_pct = pd.Series(np.nan, index=df.index)
            gap_pct[is_first_bar] = (
                (daily_open[is_first_bar] - df.loc[is_first_bar, "_prev_day_close"])
                / df.loc[is_first_bar, "_prev_day_close"].replace(0, np.nan)
            ) * 100.0
            df["gap_pct"] = gap_pct.ffill()
            df["gap_type"] = np.select(
                [df["gap_pct"] > 0.002, df["gap_pct"] < -0.002],
                ["gap_up", "gap_down"],
                default="no_gap",
            )
            df = df.drop(columns=["_prev_day_close"])

            # ── Opening Range (running high/low within IST date) ────────
            date_group = df.groupby("date")
            df["opening_range_high"] = date_group["high"].transform(
                lambda x: x.expanding().max()
            )
            df["opening_range_low"] = date_group["low"].transform(
                lambda x: x.expanding().min()
            )
            df["opening_range_breakout_pct"] = (
                (df["close"] - df["opening_range_high"]) / df["opening_range_high"].replace(0, np.nan)
            )

            # ── Session High / Low / Range (cumulative within IST date) ──
            df["day_high"] = date_group["high"].transform("cummax")
            df["day_low"] = date_group["low"].transform("cummin")
            df["day_range_pct"] = (df["day_high"] - df["day_low"]) / df["close"].replace(0, np.nan) * 100.0
            df["dist_from_day_high_pct"] = (
                (df["close"] - df["day_high"]) / df["day_high"].replace(0, np.nan) * 100.0
            )
            df["dist_from_day_low_pct"] = (
                (df["close"] - df["day_low"]) / df["day_low"].replace(0, np.nan) * 100.0
            )

            # Clean up helper columns
            df = df.drop(columns=["date"])

        else:
            logger.warning("No timestamp column — skipping session/date-based features.")

        logger.info(
            f"MarketFeatures: added minutes_since_open, session_progress, day_of_week, "
            f"session, gap_pct, gap_type, opening_range_high/low, opening_range_breakout_pct, "
            f"day_high, day_low, day_range_pct, dist_from_day_high/low_pct"
        )
        return df
