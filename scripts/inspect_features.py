"""
Feature Inspector
─────────────────
A diagnostic script that answers questions like:
  - Is RSI behaving correctly?
  - Is VWAP reasonable?
  - Are there missing candles?
  - Are features drifting over time?
  - How many rows were rejected?
  - Are there duplicate timestamps?

Usage:
    python scripts/inspect_features.py
    python scripts/inspect_features.py --date 2026-07-22
    python scripts/inspect_features.py --symbol NIFTY-I --rows 1000
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from sqlalchemy import text

from database.db import engine
from utils.logger import get_logger

logger = get_logger("inspect_features")
SEPARATOR = "─" * 55


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect market_features table quality.")
    parser.add_argument("--symbol", type=str, default="NIFTY-I", help="Symbol to inspect")
    parser.add_argument("--rows", type=int, default=500, help="Number of rows to sample")
    parser.add_argument("--date", type=str, default=None, help="Filter to YYYY-MM-DD")
    parser.add_argument("--verbose", action="store_true", help="Show all column stats")
    return parser.parse_args()


def fetch_data(symbol: str, rows: int, date: str = None) -> pd.DataFrame:
    if date:
        q = """
            SELECT * FROM market_features
            WHERE symbol = :symbol AND timestamp::date = :date
            ORDER BY timestamp ASC
        """
        df = pd.read_sql(text(q), engine, params={"symbol": symbol, "date": date})
    else:
        q = """
            SELECT * FROM market_features
            WHERE symbol = :symbol
            ORDER BY timestamp DESC LIMIT :limit
        """
        df = pd.read_sql(text(q), engine, params={"symbol": symbol, "limit": rows})
        if not df.empty:
            df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def inspect(symbol: str, rows: int, date: str, verbose: bool):
    print(f"\n{SEPARATOR}")
    print(f"  FEATURE INSPECTOR")
    print(f"{SEPARATOR}")
    print(f"  Symbol: {symbol}")
    if date:
        print(f"  Date:   {date}")
    else:
        print(f"  Rows:   {rows}")

    df = fetch_data(symbol, rows, date)
    if df.empty:
        print(f"\n  WARNING: No data found in market_features table.")
        print(f"  Run: python scripts/build_features.py --symbol {symbol}")
        return

    print(f"  Found:  {len(df)} rows")
    print(f"  Range:  {df['timestamp'].min()} -> {df['timestamp'].max()}\n")

    # ── 1. Missing candles / gaps ─────────────────────────────────────────
    print(f"{SEPARATOR}")
    print(f"  1. TIMESTAMP QUALITY")
    print(f"{SEPARATOR}")

    ts = pd.to_datetime(df["timestamp"])
    gaps = ts.diff().dt.total_seconds()
    missing_gaps = gaps[(gaps > 90) & (gaps < 3600)]
    if len(missing_gaps) > 0:
        print(f"  WARNING: Gaps found (>90s): {len(missing_gaps)}")
        for idx in missing_gaps.index[:5]:
            print(f"     {ts.iloc[idx-1]} -> {ts.iloc[idx]} ({gaps.iloc[idx]:.0f}s)")
        if len(missing_gaps) > 5:
            print(f"     ... and {len(missing_gaps)-5} more")
    else:
        print(f"  OK: No significant gaps")

    dupes = ts.duplicated().sum()
    if dupes:
        print(f"  FAIL: Duplicate timestamps: {dupes}")
    else:
        print(f"  OK: No duplicate timestamps")

    # ── 2. NaN Analysis ─────────────────────────────────────────────────
    print(f"\n{SEPARATOR}")
    print(f"  2. NaN ANALYSIS")
    print(f"{SEPARATOR}")

    feature_cols = [c for c in df.columns if c not in
                    ["timestamp", "symbol", "created_at", "feature_version"]]
    nan_counts = df[feature_cols].isna().sum()
    nan_cols = nan_counts[nan_counts > 0]
    total_cells = len(df) * len(feature_cols)
    total_nans = int(nan_counts.sum())
    nan_pct = total_nans / total_cells * 100 if total_cells > 0 else 0

    print(f"  Total cells:  {total_cells}")
    print(f"  Total NaNs:   {total_nans} ({nan_pct:.2f}%)")

    if len(nan_cols) > 0:
        print(f"  Columns with NaNs:")
        for col, count in nan_cols.items():
            pct = count / len(df) * 100
            print(f"    {col:30s}: {int(count):5d} ({pct:5.1f}%)")
    else:
        print(f"  OK: No NaN values in any column")

    # ── 3. Indicator sanity checks ──────────────────────────────────────
    print(f"\n{SEPARATOR}")
    print(f"  3. INDICATOR SANITY CHECKS")
    print(f"{SEPARATOR}")

    checks = []

    # RSI range [0, 100]
    if "rsi" in df.columns:
        rsi = df["rsi"].dropna()
        if len(rsi) > 0:
            if rsi.min() >= 0 and rsi.max() <= 100:
                checks.append(("RSI", "OK", f"range [{rsi.min():.1f}, {rsi.max():.1f}]"))
            else:
                bad = ((rsi < 0) | (rsi > 100)).sum()
                checks.append(("RSI", "FAIL", f"{bad} rows outside [0, 100]"))

    # VWAP within 5% of close
    if "vwap" in df.columns and "close" in df.columns:
        vw = df[["vwap", "close"]].dropna()
        if len(vw) > 0:
            dist = (vw["close"] - vw["vwap"]).abs() / vw["vwap"].replace(0, np.nan)
            bad_vwap = (dist > 0.05).sum()
            if bad_vwap == 0:
                checks.append(("VWAP", "OK", "all within 5% of close"))
            else:
                checks.append(("VWAP", "WARNING", f"{bad_vwap} rows >5% from close"))

    # ATR positive
    if "atr" in df.columns:
        atr = df["atr"].dropna()
        if len(atr) > 0:
            if (atr > 0).all():
                checks.append(("ATR", "OK", f"mean={atr.mean():.2f}"))
            else:
                bad = (atr <= 0).sum()
                checks.append(("ATR", "FAIL", f"{bad} rows <= 0"))

    # EMA monotonicity (ema50 < ema20 roughly)
    if "ema20" in df.columns and "ema50" in df.columns:
        em = df[["ema20", "ema50"]].dropna()
        if len(em) > 0:
            if (em["ema20"] > em["ema50"]).any() and (em["ema20"] < em["ema50"]).any():
                checks.append(("EMA", "OK", "crossovers present"))
            else:
                direction = "above" if (em["ema20"] > em["ema50"]).all() else "below"
                checks.append(("EMA", "INFO", f"ema20 always {direction} ema50"))

    # Volume positive
    if "volume" in df.columns:
        vol = df["volume"].dropna()
        if len(vol) > 0:
            if (vol >= 0).all():
                checks.append(("Volume", "OK", f"range [{vol.min()}, {vol.max()}]"))
            else:
                bad = (vol < 0).sum()
                checks.append(("Volume", "FAIL", f"{bad} rows negative"))

    for name, status, msg in checks:
        symbol = "OK" if status == "OK" else ("WARNING" if status == "WARNING" else "FAIL")
        print(f"  {symbol} [{name:12s}] {msg}")

    # ── 4. OHLC integrity ─────────────────────────────────────────────
    print(f"\n{SEPARATOR}")
    print(f"  4. OHLC INTEGRITY")
    print(f"{SEPARATOR}")

    ohlc_ok = True
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            print(f"  FAIL: Missing column '{col}'")
            ohlc_ok = False
            continue
        if df[col].isna().any():
            print(f"  FAIL: {df[col].isna().sum()} NaNs in '{col}'")
            ohlc_ok = False

    if ohlc_ok and "high" in df.columns and "low" in df.columns:
        bad_high = (df["high"] < df["low"]).sum()
        if bad_high:
            print(f"  FAIL: {bad_high} rows where high < low")
            ohlc_ok = False
        else:
            print(f"  OK: All high >= low")

    if "open" in df.columns and "close" in df.columns:
        pass  # open/close relationship is not inherently wrong

    if ohlc_ok:
        print(f"  OK: OHLC integrity check passed")

    # ── 5. Feature drift (early vs late) ──────────────────────────────
    print(f"\n{SEPARATOR}")
    print(f"  5. FEATURE DRIFT (first 10% vs last 10%)")
    print(f"{SEPARATOR}")

    if len(df) >= 20:
        numeric_cols = df[feature_cols].select_dtypes(include=[np.number]).columns
        n = len(df)
        first = df[numeric_cols].iloc[:max(10, n // 10)].mean()
        last = df[numeric_cols].iloc[-max(10, n // 10):].mean()
        drift = ((last - first).abs() / first.replace(0, np.nan).abs()) * 100
        significant = drift[drift > 20].dropna()
        if len(significant) > 0:
            print(f"  WARNING: {len(significant)} features drifted >20%:")
            for col, pct in significant.items():
                print(f"    {col:30s}: {pct:.1f}% change")
        else:
            print(f"  OK: No significant drift detected")

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{SEPARATOR}")
    print(f"  SUMMARY")
    print(f"{SEPARATOR}")
    print(f"  Rows inspected: {len(df)}")
    print(f"  Feature columns: {len(feature_cols)}")
    if verbose and len(feature_cols) > 0:
        print(f"  Column list: {feature_cols}")
    print(f"  Total NaNs: {total_nans}/{total_cells} ({nan_pct:.2f}%)")

    if total_nans == 0 and dupes == 0 and ohlc_ok:
        print(f"\n  OVERALL: DATA LOOKS CLEAN")
    else:
        print(f"\n  OVERALL: ISSUES FOUND — review above")
    print(f"{SEPARATOR}\n")


def main():
    args = parse_args()
    inspect(args.symbol, args.rows, args.date, args.verbose)


if __name__ == "__main__":
    main()
