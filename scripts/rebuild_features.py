"""
Rebuild market_features from minute_candles
=============================================
Step 1: Drop existing rows from market_features
Step 2: Load all minute_candles
Step 3: Run FeaturePipeline to recompute all features
Step 4: Verify ADX is no longer NaN
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from sqlalchemy import text
from database.db import engine, read_sql
from features.feature_engine_new import FeaturePipeline
from utils.logger import get_logger

logger = get_logger("rebuild_features")


def main():
    logger.info("=" * 60)
    logger.info("REBUILDING market_features FROM minute_candles")
    logger.info("=" * 60)

    # Step 1: Count existing
    before = read_sql("SELECT COUNT(*) as cnt FROM market_features")
    logger.info(f"Existing market_features rows: {before.iloc[0]['cnt'] if not before.empty else 0}")

    # Step 2: Truncate (delete all rows, keep table)
    logger.info("Deleting existing rows from market_features...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM market_features"))
    logger.info("Done.")

    # Step 3: Load minute_candles
    logger.info("Loading minute_candles from DB...")
    candles = read_sql(
        "SELECT * FROM minute_candles WHERE symbol = 'NIFTY-I' ORDER BY timestamp"
    )
    logger.info(f"Loaded {len(candles)} candle rows")

    if candles.empty:
        logger.error("No candles found! Aborting.")
        return

    # Step 4: Run feature pipeline
    logger.info("Running FeaturePipeline...")
    pipeline = FeaturePipeline()
    result = pipeline.run(candles, symbol="NIFTY-I", persist=True)
    logger.info(f"Feature pipeline complete. Result: {len(result)} rows")

    # Step 5: Verify
    after = read_sql("SELECT COUNT(*) as cnt FROM market_features")
    after_cnt = after.iloc[0]['cnt'] if not after.empty else 0
    logger.info(f"Rows in market_features: {after_cnt}")

    adx_check = read_sql("SELECT COUNT(*) as cnt FROM market_features WHERE adx IS NULL")
    adx_nan = adx_check.iloc[0]['cnt'] if not adx_check.empty else 0
    logger.info(f"ADX NaN rows: {adx_nan} / {after_cnt}")

    if adx_nan > 0 and after_cnt > 0:
        adx_pct = adx_nan / after_cnt * 100
        logger.info(f"ADX NaN rate: {adx_pct:.1f}% (warmup expected ~{14*4/after_cnt*100:.1f}%)")
    elif adx_nan == 0:
        logger.info("ADX: 0 NaN rows —")

    # Verify std and range
    adx_stats = read_sql(
        "SELECT MIN(adx) as min_adx, MAX(adx) as max_adx, "
        "AVG(adx) as mean_adx, STDDEV(adx) as std_adx "
        "FROM market_features WHERE adx IS NOT NULL"
    )
    if not adx_stats.empty and adx_stats.iloc[0]['min_adx'] is not None:
        s = adx_stats.iloc[0]
        logger.info(f"ADX stats: min={s['min_adx']:.2f} max={s['max_adx']:.2f} mean={s['mean_adx']:.2f} std={s['std_adx']:.2f}")
        if s['std_adx'] > 0:
            logger.info("ADX std > 0: CONFIRMED")
        else:
            logger.warning("ADX std == 0: Still broken!")
    else:
        logger.warning("ADX still all NaN after rebuild!")

    logger.info("=" * 60)
    logger.info("REBUILD COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
