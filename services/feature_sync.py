"""
Feature Sync Service
────────────────────
Thin orchestrator that keeps the market_features table in sync with new candles.

Called automatically after candles are written to minute_candles by the
AggregationEngine or by manual backfill scripts.

This is orchestration-only. It delegates to:
  1. FeaturePipeline — compute features
  2. DataValidator — validate quality
  3. FeatureStore — persist to database
"""

from typing import Optional

import pandas as pd

from features.feature_engine_new import FeaturePipeline
from utils.logger import get_logger

logger = get_logger("feature_sync")


class FeatureSyncService:
    """
    Keeps the feature store updated with the latest engineered features.

    Usage:
        sync = FeatureSyncService()
        sync.sync_latest("NIFTY-I")
        sync.sync_candle(candle_df, "NIFTY-I")
    """

    def __init__(self):
        self.pipeline = FeaturePipeline()

    def sync_candle(
        self,
        candles: pd.DataFrame,
        symbol: str = "NIFTY-I",
    ) -> int:
        """
        Process candles through the feature pipeline.

        Args:
            candles: OHLCV DataFrame (can be 1 or many rows).
            symbol: Symbol identifier.

        Returns:
            Number of feature rows persisted (0 if rejected).
        """
        if candles.empty:
            return 0

        logger.info(
            f"FeatureSync: processing {len(candles)} candle(s) for {symbol}"
        )
        features = self.pipeline.run(candles, symbol=symbol, persist=True)

        n = len(features)
        if n > 0:
            logger.info(f"FeatureSync: {n} feature row(s) stored for {symbol}")
        else:
            logger.warning(f"FeatureSync: no features persisted for {symbol}")

        return n

    def sync_latest(
        self,
        symbol: str = "NIFTY-I",
        lookback: int = 200,
    ) -> int:
        """
        Fetch the latest candles from the database and sync features.

        Args:
            symbol: Symbol to sync.
            lookback: Number of recent candles to process.

        Returns:
            Number of new feature rows persisted.
        """
        from sqlalchemy import text
        from database.db import engine

        query = text("""
            SELECT timestamp, symbol, open, high, low, close, volume
            FROM minute_candles
            WHERE symbol = :symbol
            ORDER BY timestamp DESC
            LIMIT :limit
        """)
        candles = pd.read_sql(
            query, engine, params={"symbol": symbol, "limit": lookback}
        )

        if candles.empty:
            logger.warning(f"FeatureSync: no candles found for {symbol}")
            return 0

        candles = candles.sort_values("timestamp").reset_index(drop=True)
        return self.sync_candle(candles, symbol=symbol)

    def sync_if_missing(
        self,
        symbol: str = "NIFTY-I",
        lookback: int = 200,
    ) -> int:
        """
        Sync only if the latest candle is missing from market_features.

        Args:
            symbol: Symbol to check and sync.
            lookback: Number of recent candles for indicator warmup.

        Returns:
            Number of new feature rows persisted.
        """
        from sqlalchemy import text
        from database.db import engine

        candle_q = text("""
            SELECT MAX(timestamp) as max_ts FROM minute_candles
            WHERE symbol = :symbol
        """)
        candle_result = pd.read_sql(
            candle_q, engine, params={"symbol": symbol}
        )
        if candle_result.empty or candle_result.iloc[0]["max_ts"] is None:
            return 0

        latest_candle_ts = candle_result.iloc[0]["max_ts"]

        feat_q = text("""
            SELECT 1 FROM market_features
            WHERE symbol = :symbol AND timestamp = :ts
            LIMIT 1
        """)
        feat_result = pd.read_sql(
            feat_q, engine,
            params={"symbol": symbol, "ts": latest_candle_ts},
        )

        if not feat_result.empty:
            return 0

        return self.sync_latest(symbol=symbol, lookback=lookback)
