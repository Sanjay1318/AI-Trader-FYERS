"""
PHASE 1 — END-OF-DAY LIVE SESSION AUDIT
========================================

Produces a comprehensive audit of today's (2026-07-24) live session data
across all pipeline stages: ticks → candles → features → predictions.

Usage:
    python audit/phase1_end_of_day_audit.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from sqlalchemy import text
from datetime import date, datetime, timedelta
from collections import Counter

from database.db import engine, read_sql

TODAY = date(2026, 7, 24)
TODAY_STR = TODAY.isoformat()


def print_header(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


def print_subheader(title):
    print(f"\n  --- {title} ---")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TICK DATA AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

print_header("PHASE 1: TICK DATA AUDIT")

ticks = read_sql(
    "SELECT timestamp, symbol, price, volume, bid_price, ask_price "
    "FROM tick_data WHERE timestamp::date = :dt ORDER BY timestamp",
    {"dt": TODAY_STR},
)

print(f"\n  Total ticks today: {len(ticks)}")

if not ticks.empty:
    ticks["timestamp"] = pd.to_datetime(ticks["timestamp"])
    print(f"  First tick:       {ticks['timestamp'].min()}")
    print(f"  Last tick:        {ticks['timestamp'].max()}")

    symbols = ticks["symbol"].unique()
    print(f"  Symbols:          {list(symbols)}")

    # Largest gaps
    for sym in symbols:
        sym_ticks = ticks[ticks["symbol"] == sym].sort_values("timestamp")
        gaps = sym_ticks["timestamp"].diff().dropna()
        if len(gaps) > 0:
            max_gap = gaps.max()
            max_gap_idx = gaps.idxmax()
            print(f"\n  Symbol {sym}:")
            print(f"    Total ticks:    {len(sym_ticks)}")
            print(f"    Avg gap:        {gaps.mean().total_seconds():.1f}s")
            print(f"    Median gap:     {gaps.median().total_seconds():.1f}s")
            print(f"    Max gap:        {max_gap.total_seconds():.0f}s")
            if pd.notna(max_gap_idx):
                gap_start = sym_ticks.loc[max_gap_idx - 1, "timestamp"] if max_gap_idx > 0 else sym_ticks.iloc[0]["timestamp"]
                gap_end = sym_ticks.loc[max_gap_idx, "timestamp"]
                print(f"    Gap window:     {gap_start} -> {gap_end}")
                print(f"    Gap duration:   {max_gap.total_seconds():.0f}s")
else:
    print("  ⚠️  NO TICK DATA FOUND FOR TODAY")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MINUTE CANDLES AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

print_header("PHASE 2: MINUTE CANDLES AUDIT")

candles = read_sql(
    "SELECT timestamp, symbol, open, high, low, close, volume, vwap "
    "FROM minute_candles WHERE timestamp::date = :dt ORDER BY timestamp",
    {"dt": TODAY_STR},
)

print(f"\n  Total candles today: {len(candles)}")

if not candles.empty:
    candles["timestamp"] = pd.to_datetime(candles["timestamp"])
    print(f"  First candle:  {candles['timestamp'].min()}")
    print(f"  Last candle:   {candles['timestamp'].max()}")

    symbols = candles["symbol"].unique()
    print(f"  Symbols:       {list(symbols)}")

    for sym in symbols:
        sym_c = candles[candles["symbol"] == sym].sort_values("timestamp")
        print(f"\n  Symbol {sym}:")
        print(f"    Total candles:  {len(sym_c)}")
        print(f"    First:          {sym_c['timestamp'].min()}")
        print(f"    Last:           {sym_c['timestamp'].max()}")

        # Expected trading minutes (9:15-15:30 IST = 03:45-10:00 UTC = 375 min)
        session_start = pd.Timestamp(f"{TODAY_STR} 03:45:00", tz="UTC")
        session_end = pd.Timestamp(f"{TODAY_STR} 10:00:00", tz="UTC")
        expected_minutes = set(pd.date_range(session_start, session_end, freq="1min"))

        actual_minutes = set(sym_c["timestamp"].dropna())
        missing = expected_minutes - actual_minutes
        # Filter to only weekdays
        missing_weekdays = {m for m in missing if m.weekday() < 5}
        print(f"    Missing trading mins: {len(missing_weekdays)}")
        if len(missing_weekdays) <= 20:
            for m in sorted(missing_weekdays)[:20]:
                print(f"      - {m}")

        # Duplicates
        dupes = sym_c[sym_c.duplicated(subset=["timestamp"], keep=False)]
        print(f"    Duplicate candles:   {len(dupes)}")
        if len(dupes) > 0:
            print(f"      Duplicate timestamps: {dupes['timestamp'].tolist()}")

        # OHLC integrity
        bad_ohlc = sym_c[(sym_c["high"] < sym_c["low"]) | (sym_c["high"] < sym_c["open"]) |
                         (sym_c["high"] < sym_c["close"]) | (sym_c["low"] > sym_c["open"]) |
                         (sym_c["low"] > sym_c["close"])]
        print(f"    OHLC violations:     {len(bad_ohlc)}")

        # Zero volume
        zero_vol = sym_c[sym_c["volume"] == 0]
        print(f"    Zero-volume candles: {len(zero_vol)}")

        # Stale periods (>5 min gap during trading hours)
        sym_c = sym_c.sort_values("timestamp")
        gaps = sym_c["timestamp"].diff()
        stale = gaps > pd.Timedelta(minutes=5)
        stale_count = stale.sum()
        stale_details = sym_c[stale][["timestamp"]].copy()
        if stale_count > 0:
            stale_details["gap_min"] = gaps[stale].dt.total_seconds() / 60
        print(f"    Stale periods (>5min gap): {stale_count}")
        if stale_count > 0 and len(stale_details) > 0:
            for _, row in stale_details.iterrows():
                print(f"      Gap at {row['timestamp']}: {row.get('gap_min', 0):.0f}min")

    # Summary
    print(f"\n  SUMMARY:")
    print(f"    Trading day:  {TODAY}")
    print(f"    Close price:  ₹{candles.iloc[-1]['close']:.1f}")
    print(f"    Day range:    ₹{candles['low'].min():.1f} - ₹{candles['high'].max():.1f}")
    print(f"    Volume:       {candles['volume'].sum():,.0f}")
else:
    print("  ⚠️  NO CANDLE DATA FOUND FOR TODAY")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MARKET FEATURES AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

print_header("PHASE 3: MARKET FEATURES AUDIT")

features = read_sql(
    "SELECT * FROM market_features WHERE timestamp::date = :dt ORDER BY timestamp",
    {"dt": TODAY_STR},
)

print(f"\n  Total feature rows today: {len(features)}")

if not features.empty:
    features["timestamp"] = pd.to_datetime(features["timestamp"])
    print(f"  First feature:  {features['timestamp'].min()}")
    print(f"  Last feature:   {features['timestamp'].max()}")

    symbols = features["symbol"].unique()
    print(f"  Symbols:        {list(symbols)}")

    # Duplicates
    dupes = features[features.duplicated(subset=["timestamp", "symbol"], keep=False)]
    print(f"  Duplicate rows: {len(dupes)}")
    if len(dupes) > 0:
        print(f"    Duplicate timestamps: {dupes['timestamp'].tolist()}")

    # Missing feature minutes compared to candles
    candle_ts = set(candles["timestamp"].dropna()) if not candles.empty else set()
    feature_ts = set(features["timestamp"].dropna())
    missing_features = candle_ts - feature_ts
    print(f"  Candles w/o features: {len(missing_features)}")
    if len(missing_features) <= 20:
        for ts in sorted(missing_features)[:20]:
            print(f"      {ts}")

    # NaN analysis per column
    print_subheader("NaN PERCENTAGE PER FEATURE")
    feature_cols = [c for c in features.columns
                    if c not in ("timestamp", "symbol", "created_at", "feature_version")]
    nan_pcts = features[feature_cols].isna().mean() * 100
    for col, pct in nan_pcts.items():
        if pct > 0:
            print(f"    {col:25s}: {pct:5.1f}% NaN")

    # Impossible values
    print_subheader("IMPOSSIBLE VALUES CHECK")
    if "rsi" in features.columns:
        bad_rsi = features[features["rsi"].between(0, 100) == False]["rsi"].dropna()
        print(f"    RSI outside [0,100]: {len(bad_rsi)}")
    if "atr" in features.columns:
        bad_atr = features["atr"][features["atr"] < 0].dropna()
        print(f"    ATR < 0:          {len(bad_atr)}")
    if "vwap_dist_pct" in features.columns:
        bad_vwap_dist = features[features["vwap_dist_pct"].abs() > 0.1]["vwap_dist_pct"].dropna()
        print(f"    VWAP dist > 10%:  {len(bad_vwap_dist)}")

    # Stale features (latest candle vs latest feature)
    if not candles.empty:
        latest_candle = candles["timestamp"].max()
        latest_feature = features["timestamp"].max()
        stale = (latest_candle - latest_feature).total_seconds()
        print(f"\n  Latest candle:    {latest_candle}")
        print(f"  Latest feature:   {latest_feature}")
        print(f"  Feature staleness: {stale:.0f}s")

else:
    print("  ⚠️  NO FEATURE DATA FOUND FOR TODAY")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PREDICTION HISTORY AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

print_header("PHASE 4: PREDICTION HISTORY AUDIT")

predictions = read_sql(
    "SELECT * FROM prediction_history WHERE timestamp::date = :dt ORDER BY timestamp",
    {"dt": TODAY_STR},
)

print(f"\n  Total predictions today: {len(predictions)}")

if not predictions.empty:
    predictions["timestamp"] = pd.to_datetime(predictions["timestamp"])
    print(f"  First prediction: {predictions['timestamp'].min()}")
    print(f"  Last prediction:  {predictions['timestamp'].max()}")

    # Distribution
    dist = predictions["prediction"].value_counts()
    print(f"\n  Prediction distribution:")
    for pred_type in ["bullish", "bearish", "neutral"]:
        count = dist.get(pred_type, 0)
        pct = count / len(predictions) * 100
        print(f"    {pred_type:10s}: {count:4d} ({pct:5.1f}%)")

    # Confidence statistics
    print(f"\n  Confidence stats:")
    print(f"    Average:   {predictions['confidence'].mean():.1f}")
    print(f"    Min:       {predictions['confidence'].min():.1f}")
    print(f"    Max:       {predictions['confidence'].max():.1f}")

    # Probability averages
    for col in ["bullish_probability", "bearish_probability", "neutral_probability"]:
        if col in predictions.columns:
            print(f"    {col:25s}: {predictions[col].mean():.1f}")

    # Missing outcome evaluation
    pending = predictions[predictions["correct"].isna()]
    print(f"\n  Predictions w/o outcome: {len(pending)}")
    if len(pending) > 0:
        print(f"    (Expected for same-session predictions)")

    evaluated = predictions[predictions["correct"].notna()]
    if len(evaluated) > 0:
        correct = evaluated["correct"].sum()
        total = len(evaluated)
        print(f"  Evaluated accuracy: {correct}/{total} = {correct/total*100:.1f}%")

else:
    print("  ⚠️  NO PREDICTION DATA FOUND FOR TODAY")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PAPER TRADING AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

print_header("PHASE 5: PAPER TRADING AUDIT")

# Check paper_trades file
paper_file = Path("paper_trades/trades_test.jsonl")
if paper_file.exists():
    lines = paper_file.read_text().splitlines()
    trades = []
    for line in lines:
        if line.strip():
            import json
            trades.append(json.loads(line))
    print(f"\n  Total recorded trades: {len(trades)}")
    if trades:
        wins = sum(1 for t in trades if t.get("pnl", 0) or t.get("realised_pnl", 0) or 0 > 0)
        losses = sum(1 for t in trades if (t.get("pnl", 0) or t.get("realised_pnl", 0) or 0) <= 0)
        total_pnl = sum(t.get("pnl", 0) or t.get("realised_pnl", 0) or 0 for t in trades)
        print(f"    Wins/Losses:  {wins}/{losses}")
        print(f"    Total P&L:    ₹{total_pnl:.2f}")
else:
    print("  No paper trade file found.")


print(f"\n{'='*65}")
print(f"  AUDIT COMPLETE — {TODAY}")
print(f"{'='*65}\n")
