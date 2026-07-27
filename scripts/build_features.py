"""
Build Historical Feature Dataset
─────────────────────────────────
CLI entry point for generating market_features from historical minute_candles
using the new FeaturePipeline.

Usage:
    python scripts/build_features.py --all                          # All available data
    python scripts/build_features.py --symbol NIFTY-I               # Single symbol
    python scripts/build_features.py --start 2026-07-01 --end 2026-07-24
    python scripts/build_features.py --validate                     # Dry-run: check warmup + NaN

The script uses the existing FeaturePipeline (FeatureEngineNew) and FeatureStore.
No feature logic is duplicated here.
"""

import sys
import os
import argparse
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import pandas as pd

from database.db import read_sql
from features.feature_engine_new import FeaturePipeline
from utils.logger import get_logger

logger = get_logger("build_features")

# Warmup required for EMA50 = 51 candles
MAX_WARMUP = 51


def parse_args():
    parser = argparse.ArgumentParser(description="Build historical feature dataset")
    parser.add_argument("--symbol", type=str, default="NIFTY-I")
    parser.add_argument("--all", action="store_true", help="Process all available data")
    parser.add_argument("--start", type=str, default="", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default="", help="End date YYYY-MM-DD")
    parser.add_argument("--validate", action="store_true", help="Validate only (dry-run)")
    parser.add_argument("--days", type=int, default=0, help="Number of recent days")
    return parser.parse_args()


def load_candles(symbol, start_date=None, end_date=None):
    """Load candles from DB for the given symbol and date range."""
    query = """SELECT timestamp, symbol, open, high, low, close, volume, vwap
               FROM minute_candles WHERE symbol = :symbol"""
    params = {"symbol": symbol}
    if start_date:
        query += " AND timestamp >= :start"
        params["start"] = start_date
    if end_date:
        query += " AND timestamp <= :end"
        params["end"] = end_date
    query += " ORDER BY timestamp"
    df = read_sql(query, params)
    if df.empty:
        logger.warning(f"No candles found for {symbol}")
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def main():
    args = parse_args()

    logger.info("=" * 60)
    logger.info("  BUILD HISTORICAL FEATURES")
    logger.info("=" * 60)

    pipeline = FeaturePipeline()

    if args.all:
        start_date, end_date = None, None
        logger.info("  Mode: ALL available data")
    elif args.start and args.end:
        start_date, end_date = args.start, args.end
    elif args.days > 0:
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=args.days)).isoformat()
    elif args.validate:
        start_date, end_date = None, None
    else:
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=10)).isoformat()
        logger.info(f"  Mode: Last 10 days ({start_date} -> {end_date})")

    if start_date:
        warmup_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=3)).strftime("%Y-%m-%d")
        df = load_candles(args.symbol, warmup_start, end_date)
        logger.info(f"  Loaded {len(df)} candles ({warmup_start} -> {end_date}) + warmup")
    else:
        df = load_candles(args.symbol)
        logger.info(f"  Loaded {len(df)} candles (all available)")

    if df.empty:
        logger.error("No data to process.")
        return 1

    trading_days = df["timestamp"].dt.date.nunique()
    logger.info(f"  Trading days: {trading_days}")
    logger.info(f"  Range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

    if args.validate:
        logger.info("\n--- VALIDATION MODE (no writes) ---")
        post = df.tail(len(df) - MAX_WARMUP)
        logger.info(f"  Post-warmup: {len(post)} rows ({len(post)/max(len(df),1)*100:.1f}%)")
        return 0

    # Compute features
    logger.info("\n  Computing features...")
    featured = pipeline.run(df, symbol=args.symbol, persist=False)
    logger.info(f"  Rows: {len(featured)}, Cols: {len(featured.columns)}")

    # NaN stats
    non_id = [c for c in featured.columns if c not in ("timestamp", "symbol", "created_at", "feature_version")]
    nan_n = featured[non_id].isna().sum().sum()
    nan_t = len(featured) * len(non_id)
    logger.info(f"  NaN rate: {nan_n/nan_t*100:.2f}% ({nan_n}/{nan_t})")

    # Store
    logger.info("\n  Storing to market_features...")
    from features.feature_store import insert_features
    pipeline.ensure_storage()
    inserted = insert_features(featured)
    logger.info(f"  Stored {inserted} rows")

    logger.info("\n" + "=" * 60)
    logger.info("  FEATURE BUILD COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Candles: {len(df)}")
    logger.info(f"  Features: {len(featured)}")
    logger.info(f"  Stored: {inserted}")
    logger.info(f"  Days: {trading_days}")
    logger.info(f"  Range: {featured['timestamp'].min().date()} -> {featured['timestamp'].max().date()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
