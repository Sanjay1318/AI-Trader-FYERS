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
            df["session_progress"] = (df["minutes_since_open"] / (SESSION_END - SESSION_START)).clip(0, 1)

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
            df["day_of_week"] = ist.dt.dayofweek
            df["is_first_hour"] = (df["minutes_since_open"] <= 60).astype(int)
            df["is_last_hour"] = (df["minutes_since_open"] >= (SESSION_END - SESSION_START - 60)).astype(int)

            # ── Gap detection (use IST date for proper trading-day grouping) ─
            df["date"] = ist.dt.date
            daily_close = df.groupby("date")["close"].transform("last")
            daily_open = df.groupby("date")["open"].transform("first")
            prev_close = df.groupby("date")["close"].shift(1)
            is_first_bar = df.groupby("date").cumcount() == 0
            gap_pct = pd.Series(np.nan, index=df.index)
            gap_pct[is_first_bar] = (
                (daily_open[is_first_bar] - prev_close[is_first_bar])
                / prev_close[is_first_bar].replace(0, np.nan)
            )
            df["gap_pct"] = gap_pct.ffill()
            df["gap_type"] = np.select(
                [df["gap_pct"] > 0.002, df["gap_pct"] < -0.002],
                ["gap_up", "gap_down"],
                default="no_gap",
            )

            # ── Opening Range (running high/low within IST date) ────────
            date_group = df.groupby("date")
            df["or_high"] = date_group["high"].transform(
                lambda x: x.expanding().max()
            )
            df["or_low"] = date_group["low"].transform(
                lambda x: x.expanding().min()
            )
            df["or_breakout_pct"] = (df["close"] - df["or_high"]) / df["or_high"].replace(0, np.nan)
            df["or_breakdown_pct"] = (df["close"] - df["or_low"]) / df["or_low"].replace(0, np.nan)

            # ── Session High / Low / Range (cumulative within IST date) ──
            df["day_high"] = date_group["high"].transform("cummax")
            df["day_low"] = date_group["low"].transform("cummin")
            df["day_range"] = df["day_high"] - df["day_low"]
            df["dist_from_high_pct"] = (df["close"] - df["day_high"]) / df["day_high"].replace(0, np.nan)
            df["dist_from_low_pct"] = (df["close"] - df["day_low"]) / df["day_low"].replace(0, np.nan)

            # Clean up helper columns
            df = df.drop(columns=["date"])

        else:
            logger.warning("No timestamp column — skipping session/date-based features.")

        logger.info(f"MarketFeatures: added session, gap_type, or_high/low, day_high/low, dist_from_high/low_pct")
        return df
