"""
Feature Backfill
────────────────
Generates features for historical data ranges so we have training data ready.

Usage:
    python scripts/backfill_features.py --days 7
    python scripts/backfill_features.py --start 2026-07-01 --end 2026-07-22
    python scripts/backfill_features.py --last-week
    python scripts/backfill_features.py --last-month
    python scripts/backfill_features.py --last-year
"""

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlalchemy import text

from database.db import engine
from features.feature_engine_new import FeaturePipeline
from features.feature_store import create_table, table_exists, insert_features
from utils.logger import get_logger

logger = get_logger("backfill_features")


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill features for historical data.")
    parser.add_argument("--symbol", type=str, default="NIFTY-I", help="Symbol to process")
    parser.add_argument("--days", type=int, default=None, help="Number of recent days to backfill")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--last-week", action="store_true", help="Backfill last 7 days")
    parser.add_argument("--last-month", action="store_true", help="Backfill last 30 days")
    parser.add_argument("--last-year", action="store_true", help="Backfill last 365 days")
    parser.add_argument("--chunk-size", type=int, default=500, help="Candles per chunk")
    parser.add_argument("--dry-run", action="store_true", help="Print without inserting")
    parser.add_argument("--verbose", action="store_true", help="Show per-day progress")
    return parser.parse_args()


def get_available_dates(symbol: str) -> list:
    """Return sorted list of dates that have candle data for the symbol."""
    q = """
        SELECT DISTINCT timestamp::date as day
        FROM minute_candles
        WHERE symbol = :symbol
        ORDER BY day
    """
    df = pd.read_sql(text(q), engine, params={"symbol": symbol})
    return df["day"].tolist() if not df.empty else []


def get_already_done_dates(symbol: str) -> set:
    """Return set of dates that already have features in market_features."""
    q = """
        SELECT DISTINCT timestamp::date as day
        FROM market_features
        WHERE symbol = :symbol
    """
    df = pd.read_sql(text(q), engine, params={"symbol": symbol})
    return set(df["day"].tolist()) if not df.empty else set()


def backfill_range(symbol, date_list, dry_run, verbose, already_done):
    """Backfill features for each date in date_list."""
    pipeline = FeaturePipeline()
    total_candles = 0
    total_features = 0
    total_skipped = 0
    start_time = time.time()

    for i, d in enumerate(date_list):
        if d in already_done:
            total_skipped += 1
            if verbose:
                print(f"  SKIP {d} (already has features)")
            continue

        q = """
            SELECT timestamp, symbol, open, high, low, close, volume
            FROM minute_candles
            WHERE symbol = :symbol AND timestamp::date = :date
            ORDER BY timestamp ASC
        """
        candles = pd.read_sql(text(q), engine, params={"symbol": symbol, "date": d})

        if candles.empty:
            if verbose:
                print(f"  SKIP {d} (no candles)")
            total_skipped += 1
            continue

        total_candles += len(candles)

        if dry_run:
            print(f"  WOULD PROCESS {d}: {len(candles)} candles")
            continue

        try:
            features = pipeline.run(candles, symbol=symbol, persist=not dry_run)
            n = len(features)
            total_features += n
            if verbose or i % 10 == 0:
                print(f"  {d}: {len(candles)} candles -> {n} features")
        except Exception as e:
            print(f"  ERROR {d}: {e}")

        time.sleep(0.1)

    elapsed = time.time() - start_time
    return total_candles, total_features, total_skipped, elapsed


def main():
    args = parse_args()

    today = date.today()
    if args.last_week:
        start = today - timedelta(days=7)
        end = today
    elif args.last_month:
        start = today - timedelta(days=30)
        end = today
    elif args.last_year:
        start = today - timedelta(days=365)
        end = today
    elif args.days:
        start = today - timedelta(days=args.days)
        end = today
    elif args.start:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end) if args.end else today
    else:
        start = today - timedelta(days=7)
        end = today

    print(f"\n{'='*55}")
    print(f"  FEATURE BACKFILL")
    print(f"{'='*55}")
    print(f"  Symbol: {args.symbol}")
    print(f"  Range:  {start} -> {end}")
    print(f"  Mode:   {'DRY RUN' if args.dry_run else 'PERSIST'}")

    if not args.dry_run and not table_exists():
        create_table()
        print(f"  Created market_features table.")

    all_dates = get_available_dates(args.symbol)
    in_range = [d for d in all_dates if start <= d <= end]

    if not in_range:
        print(f"\n  No candle data found for {args.symbol} in range {start} -> {end}")
        return

    print(f"\n  Dates found: {len(in_range)}")
    already = get_already_done_dates(args.symbol)
    if already:
        print(f"  Already have features for: {len(already)} dates")

    candles, features, skipped, elapsed = backfill_range(
        args.symbol, in_range, args.dry_run, args.verbose, already
    )

    print(f"\n{'='*55}")
    print(f"  BACKFILL COMPLETE")
    print(f"{'='*55}")
    print(f"  Processed: {len(in_range) - skipped} dates")
    print(f"  Skipped:   {skipped} dates")
    print(f"  Candles:   {candles}")
    print(f"  Features:  {features}")
    print(f"  Time:      {elapsed:.1f}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
