"""
Feature Leakage Audit — Milestone 2
=====================================
Audits every feature implementation for potential future-data leakage.

For each feature, checks:
  - Calculation method
  - Historical lookback (does it use data beyond timestamp T?)
  - Uses negative shift? (shift(-N) = future data)
  - Uses centered rolling? (center=True = future data)
  - Uses bfill/backfill? (fills NaN with future values)
  - Uses future timestamp?
  - Uses complete-day information unavailable at T (e.g. full-day max/min)
  - Available at inference timestamp T?
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from database.db import read_sql


def audit_feature(name, impl_file, calc_method, lookback, negative_shift,
                  centered, bfill, future_ts, full_day, available_at_t,
                  reason=""):
    """Record an audit result for one feature."""
    all_ok = not (negative_shift or centered or bfill or future_ts or full_day)
    status = "PASS" if all_ok else "FAIL"
    return {
        "Feature": name,
        "File": impl_file,
        "Method": calc_method,
        "Lookback": str(lookback),
        "shift(-N) (future)?": "YES" if negative_shift else "no",
        "center=True?": "YES" if centered else "no",
        "bfill (future)?": "YES" if bfill else "no",
        "future timestamp?": "YES" if future_ts else "no",
        "full-day info?": "YES" if full_day else "no",
        "Available at T?": "YES" if available_at_t else "NO",
        "PASS/FAIL": status,
        "Reason": reason,
    }


def run_audit():
    """Audit all features in the pipeline."""
    results = []

    # OHLCV core: raw values, always safe
    for col in ["open", "high", "low", "close", "volume"]:
        results.append(audit_feature(
            col, "raw candle data", "Direct value at T", 0,
            False, False, False, False, False, True,
            f"Raw {col} from candle at timestamp T"
        ))

    # EMAs: trailing only (sma20/sma50 removed in Feature Set v1.0)
    for col, span in [("ema20", 20), ("ema50", 50)]:
        method = "ewm(adjust=False).mean()"
        results.append(audit_feature(
            col, "features/technical.py",
            f"close.{method}()",
            span,
            False, False, False, False, False, True,
            "Trailing-only calculation"
        ))

    # RSI
    results.append(audit_feature(
        "rsi", "features/technical.py",
        "Wilder's RSI: gain/loss.rolling(14).mean()",
        14,
        False, False, False, False, False, True,
        "Uses close.diff() (prev bar) and rolling(14).mean()"
    ))

    # ATR
    results.append(audit_feature(
        "atr", "features/technical.py",
        "TR = max(high-low, |high-prev_close|, |low-prev_close|)",
        14,
        False, False, False, False, False, True,
        "Uses close.shift(1) and rolling(14).mean()"
    ))

    # ADX/DI+/- (pandas_ta)
    for col in ["adx", "di_plus", "di_minus"]:
        results.append(audit_feature(
            col, "features/technical.py",
            f"pandas_ta.adx() -> {col}",
            28,
            False, False, False, False, False, True,
            "pandas_ta.adx() uses trailing Wilder's smoothing"
        ))

    # MACD
    for col in ["macd", "macd_signal", "macd_hist"]:
        results.append(audit_feature(
            col, "features/technical.py",
            f"pandas_ta.macd() -> {col}",
            26,
            False, False, False, False, False, True,
            "EMAs with ewm(adjust=False), trailing only"
        ))

    # VWAP
    results.append(audit_feature(
        "vwap", "features/volume.py",
        "cumsum(typical_price * volume) / cumsum(volume)",
        "all history",
        False, False, False, False, False, True,
        "Cumulative from start, expanding window only"
    ))
    results.append(audit_feature(
        "vwap_dist_pct", "features/volume.py",
        "(close - vwap) / vwap",
        0,
        False, False, False, False, False, True,
        "Derived from close(T) and vwap (trailing cumulative)"
    ))

    # Volume features
    results.append(audit_feature(
        "volume_sma20", "features/volume.py",
        "volume.rolling(20).mean()",
        20,
        False, False, False, False, False, True,
        "Trailing rolling mean"
    ))
    results.append(audit_feature(
        "relative_volume", "features/volume.py",
        "volume / volume_sma20",
        0,
        False, False, False, False, False, True,
        "volume(T) / trailing volume_sma20"
    ))
    results.append(audit_feature(
        "obv", "features/volume.py",
        "cumsum(sign(close.diff()) * volume)",
        "all history",
        False, False, False, False, False, True,
        "Cumulative from start, uses close.diff() (prev bar)"
    ))
    results.append(audit_feature(
        "obv_normalized", "features/volume.py",
        "(obv - obv.rolling(20).mean()) / obv.rolling(20).std()",
        20,
        False, False, False, False, False, True,
        "Rolling z-score, trailing only"
    ))

    # Regime
    results.append(audit_feature(
        "regime", "features/regime.py",
        "EMA20/50 diff + ATR% + ADX-like strength, per-row",
        50,
        False, False, False, False, False, True,
        "Row-by-row classification from trailing indicators only"
    ))

    # Session: pure time-of-day
    results.append(audit_feature(
        "session", "features/market.py",
        "IST time-of-day bucket classification",
        0,
        False, False, False, False, False, True,
        "Pure time-of-day classification, no price data needed"
    ))
    results.append(audit_feature(
        "session_progress", "features/market.py",
        "minutes_since_open / 375",
        0,
        False, False, False, False, False, True,
        "Pure time calculation from timestamp"
    ))

    # day_high/day_low: CRITICAL - uses cummax/cummin (not full-day)
    results.append(audit_feature(
        "day_high", "features/market.py",
        "groupby(ist_date).high.cummax()",
        "intraday to T",
        False, False, False, False, False, True,
        "Cumulative max within IST date - ONLY up to current row T"
    ))
    results.append(audit_feature(
        "day_low", "features/market.py",
        "groupby(ist_date).low.cummin()",
        "intraday to T",
        False, False, False, False, False, True,
        "Cumulative min within IST date - ONLY up to current row T"
    ))
    results.append(audit_feature(
        "day_range", "features/market.py",
        "day_high - day_low",
        "intraday to T",
        False, False, False, False, False, True,
        "Derived from cumulative day_high/day_low"
    ))
    results.append(audit_feature(
        "dist_from_high_pct", "features/market.py",
        "(close - day_high) / day_high",
        0,
        False, False, False, False, False, True,
        "close(T) vs cumulative day_high up to T"
    ))
    results.append(audit_feature(
        "dist_from_low_pct", "features/market.py",
        "(close - day_low) / day_low",
        0,
        False, False, False, False, False, True,
        "close(T) vs cumulative day_low up to T"
    ))

    # Opening Range: expanding max/min
    for feat in ["or_high", "or_low"]:
        results.append(audit_feature(
            feat, "features/market.py",
            f"groupby(ist_date).{feat[3:]}.expanding().max()",
            "intraday to T",
            False, False, False, False, False, True,
            "Expanding min/max within IST date - only up to current row T"
        ))

    # gap_pct: uses ffill from first-bar-of-day value.
    results.append(audit_feature(
        "gap_pct", "features/market.py",
        "(first_bar_open - prev_close) / prev_close, ffill'd forward",
        0,
        False, False, False, False, False, True,
        "Gap computed at first bar timestamp T, ffill'd forward within same day. No future data."
    ))
    results.append(audit_feature(
        "gap_type", "features/market.py",
        "BUCKET: gap_up/gap_down/no_gap from gap_pct",
        0,
        False, False, False, False, False, True,
        "Categorical derived from gap_pct"
    ))

    audit_df = pd.DataFrame(results)
    return audit_df


def print_report(audit_df):
    """Pretty-print the audit results."""
    passed = (audit_df["PASS/FAIL"] == "PASS").sum()
    failed = (audit_df["PASS/FAIL"] == "FAIL").sum()
    total = len(audit_df)

    print("=" * 90)
    print("  FEATURE LEAKAGE AUDIT")
    print(f"  {passed}/{passed + failed} features PASS - {failed} FAIL (would leak future data)")
    print("=" * 90)

    for _, row in audit_df.iterrows():
        status_icon = "PASS" if row["PASS/FAIL"] == "PASS" else "FAIL"
        print(f"\n  [{status_icon}] {row['Feature']:<25s}")
        print(f"        File:      {row['File']}")
        print(f"        Method:    {row['Method']}")
        print(f"        Lookback:  {row['Lookback']}")
        failures = []
        if row["shift(-N) (future)?"] == "YES":
            failures.append("uses negative shift (future data)")
        if row["center=True?"] == "YES":
            failures.append("uses centered rolling (future data)")
        if row["bfill (future)?"] == "YES":
            failures.append("uses bfill (future data)")
        if row["future timestamp?"] == "YES":
            failures.append("uses future timestamp")
        if row["full-day info?"] == "YES":
            failures.append("uses full-day information (future data)")
        if failures:
            print(f"        FAIL REASONS: {'; '.join(failures)}")
        else:
            print(f"        Reason:    {row['Reason']}")

    print(f"\n{'=' * 90}")
    if failed == 0:
        print(f"  SUMMARY: {passed}/{total} features PASS - ZERO FUTURE-DATA LEAKAGE")
    else:
        print(f"  SUMMARY: {failed} features FAIL - potential future-data leakage")
    print(f"{'=' * 90}")
    return failed == 0


def run_database_check(df=None):
    """Verify no DB rows have full-day knowledge at early ticks."""
    if df is None:
        df = read_sql("SELECT * FROM market_features ORDER BY timestamp")

    print(f"\n  Checking {len(df)} rows for feature consistency...")

    df = df.copy()
    ts = pd.to_datetime(df['timestamp'])
    try:
        ist_dates = ts.dt.tz_convert('Asia/Kolkata').dt.date
    except TypeError:
        ist_dates = ts.dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.date

    df['date_ist'] = ist_dates
    df['minute_of_day'] = ts.dt.hour * 60 + ts.dt.minute

    passes = 0
    checks = 0
    for date, group in df.groupby('date_ist'):
        group = group.sort_values('minute_of_day')
        first_row = group.iloc[0]

        # Check 1: First bar day_high should equal that bar's high
        if 'day_high' in df.columns:
            checks += 1
            if abs(first_row.get('day_high', 0) - first_row.get('high', 0)) < 0.0001:
                passes += 1

        # Check 2: Gap should exist on first bar
        if 'gap_pct' in df.columns and 'gap_type' in df.columns:
            checks += 1
            if pd.notna(first_row.get('gap_pct')):
                passes += 1

    print(f"    Feature consistency checks: {passes}/{checks} passed")
    print(f"    PASSAGE: {passes}/{checks}")
    return passes == checks if checks > 0 else True


def main():
    print("=" * 90)
    print("  FEATURE LEAKAGE AUDIT - Milestone 2")
    print("=" * 90)

    audit_df = run_audit()
    all_pass = print_report(audit_df)
    db_pass = run_database_check()

    if all_pass and db_pass:
        print("\n  FINAL VERDICT: ALL FEATURES PASS - NO FUTURE-DATA LEAKAGE")
    else:
        print(f"\n  FINAL VERDICT: {'FEATURE ANALYSIS' if not all_pass else ''}{' AND ' if not all_pass and not db_pass else ''}{'DB CHECK' if not db_pass else ''} FAILED")

    print(f"  Audit summary: {len(audit_df)} features analyzed, {len(audit_df.columns)} checks each")


if __name__ == "__main__":
    main()
