"""
FYERS Historical Candle Backfill
──────────────────────────────────
Downloads historical 1-minute NIFTY index candles from FYERS API
and stores them in minute_candles table.

Usage:
    python scripts/backfill_fyers_history.py --months 1
    python scripts/backfill_fyers_history.py --months 6
    python scripts/backfill_fyers_history.py --start 2026-01-01 --end 2026-07-24
    python scripts/backfill_fyers_history.py --all          # max available
    python scripts/backfill_fyers_history.py --validate     # dry-run + validate only

Idempotent: safe to run multiple times (uses upsert by timestamp+symbol).
"""

import sys, os, time, json
from datetime import datetime, timedelta, date, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import argparse
import numpy as np
import pandas as pd

from config.settings import FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN
from database.db import engine, read_sql
from utils.logger import get_logger

logger = get_logger("backfill_fyers_history")

# ── Configuration ─────────────────────────────────────────────────────────────
FYERS_SYMBOL = "NSE:NIFTY50-INDEX"
STORAGE_SYMBOL = "NIFTY-I"  # what we store in DB
RESOLUTION = "1"             # 1-minute candles
BATCH_DAYS = 25              # FYERS max range without error (30 days works, 180 fails)
RATE_LIMIT_DELAY = 0.5       # seconds between API calls
MAX_RETRIES = 3
BACKOFF_BASE = 2.0           # exponential backoff multiplier


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill historical NIFTY candles from FYERS")
    parser.add_argument("--months", type=int, default=0, help="Number of months to backfill")
    parser.add_argument("--start", type=str, default="", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default="", help="End date YYYY-MM-DD")
    parser.add_argument("--all", action="store_true", help="Backfill all available history (max ~30 days per batch)")
    parser.add_argument("--validate", action="store_true", help="Validate existing data without downloading")
    return parser.parse_args()


def get_fyers_client():
    """Get authenticated FYERS API client."""
    from fyers_apiv3 import fyersModel
    client = fyersModel.FyersModel(
        client_id=FYERS_CLIENT_ID,
        token=FYERS_ACCESS_TOKEN,
        is_async=False,
        log_path="",
    )
    # Verify connection
    profile = client.get_profile()
    if profile.get("s") != "ok":
        raise ConnectionError(f"FYERS auth failed: {profile}")
    logger.info("FYERS client authenticated successfully")
    return client


def fetch_batch(client, from_date: str, to_date: str) -> list:
    """
    Fetch one batch of 1-minute candles from FYERS.
    Returns list of candle arrays: [epoch, open, high, low, close, volume]
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.history(data={
                "symbol": FYERS_SYMBOL,
                "resolution": RESOLUTION,
                "date_format": "1",
                "range_from": from_date,
                "range_to": to_date,
                "cont_flag": "1",
            })
            status = resp.get("s")
            if status == "ok":
                candles = resp.get("candles", [])
                if candles:
                    logger.info(f"  Fetched {len(candles)} candles: {from_date} -> {to_date}")
                else:
                    logger.warning(f"  No data: {from_date} -> {to_date}")
                return candles
            elif status == "no_data":
                logger.debug(f"  No data available: {from_date} -> {to_date}")
                return []
            else:
                msg = resp.get("message", "unknown error")
                logger.warning(f"  FYERS error (attempt {attempt+1}): {msg}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF_BASE ** attempt * 2)
                continue
        except Exception as e:
            logger.error(f"  Request failed (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE ** attempt * 2)
            continue
    logger.error(f"  Failed after {MAX_RETRIES} attempts: {from_date} -> {to_date}")
    return []


def candles_to_dataframe(candles: list) -> pd.DataFrame:
    """
    Convert FYERS candle arrays to DataFrame matching minute_candles schema.
    Candle format: [epoch, open, high, low, close, volume]
    """
    if not candles:
        return pd.DataFrame()

    rows = []
    for c in candles:
        ts = datetime.fromtimestamp(c[0], tz=timezone.utc)
        rows.append({
            "timestamp": ts,
            "symbol": STORAGE_SYMBOL,
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": int(c[5]),
            "vwap": 0.0,  # Not provided by FYERS history; computed later
        })

    df = pd.DataFrame(rows)

    # Market hours filter: only 03:45-10:00 UTC (09:15-15:30 IST)
    df["_hour"] = df["timestamp"].dt.hour
    df["_minute"] = df["timestamp"].dt.minute
    df["_minutes_from_midnight"] = df["_hour"] * 60 + df["_minute"]

    # Market hours: 03:45 UTC = 225 min, 10:00 UTC = 600 min
    market_mask = (df["_minutes_from_midnight"] >= 225) & (df["_minutes_from_midnight"] <= 599)
    df = df[market_mask].copy()

    # Remove helper columns
    df.drop(columns=["_hour", "_minute", "_minutes_from_midnight"], inplace=True)

    # Drop duplicates (same timestamp can occur at batch boundaries)
    df.drop_duplicates(subset=["timestamp", "symbol"], keep="last", inplace=True)

    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


def generate_date_batches(start: date, end: date) -> list:
    """Split date range into BATCH_DAYS-sized chunks."""
    batches = []
    current = start
    while current < end:
        batch_end = min(current + timedelta(days=BATCH_DAYS - 1), end)
        batches.append((current.isoformat(), batch_end.isoformat()))
        current = batch_end + timedelta(days=1)
        time.sleep(0.1)  # Don't overwhelm anything
    return batches


def upsert_candles(df: pd.DataFrame) -> int:
    """Upsert candles to minute_candles table, returning count of new rows."""
    if df.empty:
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy import Table, MetaData, text

    meta = MetaData()
    meta.reflect(bind=engine, only=["minute_candles"])
    tbl = meta.tables["minute_candles"]

    rows = df.to_dict(orient="records")
    inserted = 0
    with engine.begin() as conn:
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            stmt = pg_insert(tbl).values(chunk).on_conflict_do_nothing(
                index_elements=["timestamp", "symbol"]
            )
            result = conn.execute(stmt)
            inserted += result.rowcount
    return inserted


def validate_existing_data():
    """Validate existing minute_candles and report quality."""
    logger.info("\n--- Validating existing candle data ---")

    df = read_sql(
        "SELECT timestamp, symbol, open, high, low, close, volume "
        "FROM minute_candles WHERE symbol = :sym ORDER BY timestamp",
        {"sym": STORAGE_SYMBOL},
    )

    if df.empty:
        logger.warning("No existing data found in minute_candles")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    total = len(df)
    days = df["timestamp"].dt.date.nunique()
    logger.info(f"Total candles: {total}")
    logger.info(f"Trading days:  {days}")
    logger.info(f"Oldest:        {df['timestamp'].min()}")
    logger.info(f"Newest:        {df['timestamp'].max()}")

    # Per-day breakdown
    logger.info("\nCandles per day:")
    for d, grp in df.groupby(df["timestamp"].dt.date):
        c = len(grp)
        expected = 375
        status = "OK" if c >= 370 else f"MISSING ({c}/{expected})"
        logger.info(f"  {d}: {c} candles - {status}")

    # Data quality
    bad_ohlc = df[(df["high"] < df["low"]) | (df["high"] < df["close"]) | (df["low"] > df["close"])]
    if len(bad_ohlc) > 0:
        logger.warning(f"OHLC violations: {len(bad_ohlc)}")

    zero_vol = (df["volume"] == 0).sum()
    if zero_vol > 0:
        logger.warning(f"Zero-volume candles: {zero_vol} ({zero_vol/total*100:.1f}%)")

    dupes = df.duplicated(subset=["timestamp", "symbol"]).sum()
    if dupes > 0:
        logger.warning(f"Duplicate rows: {dupes}")


def main():
    args = parse_args()

    logger.info("=" * 60)
    logger.info("  FYERS HISTORICAL CANDLE BACKFILL")
    logger.info("=" * 60)
    logger.info(f"  FYERS symbol:   {FYERS_SYMBOL}")
    logger.info(f"  Storage symbol: {STORAGE_SYMBOL}")
    logger.info(f"  Resolution:     {RESOLUTION} min")
    logger.info(f"  Batch size:     {BATCH_DAYS} days")

    # ── Validate only mode ──────────────────────────────────────────────
    if args.validate:
        validate_existing_data()
        return

    # ── Determine date range ────────────────────────────────────────────
    today = date.today()

    if args.start and args.end:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    elif args.months > 0:
        end_date = today
        start_date = end_date - timedelta(days=args.months * 30)
    elif args.all:
        # FYERS max continuous history: go back 40 days to be safe
        end_date = today
        start_date = end_date - timedelta(days=40)
    else:
        # Default: last 10 trading days
        end_date = today
        start_date = end_date - timedelta(days=14)

    logger.info(f"\n  Date range: {start_date} -> {end_date}")

    # ── Generate batches ────────────────────────────────────────────────
    batches = generate_date_batches(start_date, end_date)
    logger.info(f"  Batches: {len(batches)}")

    # ── Fetch all candles ───────────────────────────────────────────────
    client = get_fyers_client()
    all_candles = []

    for i, (frm, to) in enumerate(batches):
        logger.info(f"\nBatch {i+1}/{len(batches)}: {frm} -> {to}")
        candles = fetch_batch(client, frm, to)
        all_candles.extend(candles)
        time.sleep(RATE_LIMIT_DELAY)

    logger.info(f"\n  Total raw candles fetched: {len(all_candles)}")

    if not all_candles:
        logger.warning("No data fetched. Nothing to store.")
        return

    # ── Convert to DataFrame ────────────────────────────────────────────
    df = candles_to_dataframe(all_candles)
    logger.info(f"  After market-hours filter: {len(df)} candles")
    logger.info(f"  Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    logger.info(f"  Trading days: {df['timestamp'].dt.date.nunique()}")

    # ── Upsert to DB ────────────────────────────────────────────────────
    inserted = upsert_candles(df)
    logger.info(f"\n  Inserted {inserted} new candles (duplicates skipped)")

    # ── Validation report ──────────────────────────────────────────────
    validate_existing_data()

    logger.info("\n" + "=" * 60)
    logger.info("  BACKFILL COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
