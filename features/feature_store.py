"""
Feature Store — Persistence Layer
──────────────────────────────────
Strictly database operations for the market_features table.

No calculations live here. This module only:
  - Creates the table
  - Inserts rows
  - Updates rows
  - Fetches latest feature row
  - Fetches feature history
  - Deletes duplicates
"""

from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy import Table, MetaData, Column, String, BigInteger, Integer, Float, DateTime

from database.db import engine, get_connection
from utils.logger import get_logger

logger = get_logger("feature_store")

# ── Table Name ────────────────────────────────────────────────────────────────

MARKET_FEATURES_TABLE = "market_features"

# ── Column Schema (FEATURE SET v1.0) ──────────────────────────────────────────

# Core OHLCV
BASE_COLUMNS = [
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
]

# Technical indicators + derived relative-price features
# sma20/sma50 removed (r=0.9996 vs ema20/ema50 — zero independent signal)
TECHNICAL_COLUMNS = [
    "ema20",
    "ema50",
    "rsi",
    "atr",
    "adx",
    "di_plus",
    "di_minus",
    "macd",
    "macd_signal",
    "macd_hist",
    "return_1m",
    "return_3m",
    "return_5m",
    "high_low_pct",
    "close_open_pct",
    "body_pct",
    "rolling_volatility",
]

# Volume indicators
VOLUME_COLUMNS = [
    "vwap",
    "vwap_dist_pct",
    "volume_sma20",
    "relative_volume",
    "obv",
    "obv_normalized",
    "log_volume",
]

# Market context (session, regime, gap, day-range features)
MARKET_COLUMNS = [
    "regime",
    "session",
    "minutes_since_open",
    "session_progress",
    "day_of_week",
    "gap_pct",
    "gap_type",
    "opening_range_high",
    "opening_range_low",
    "opening_range_breakout_pct",
    "day_high",
    "day_low",
    "day_range_pct",
    "dist_from_day_high_pct",
    "dist_from_day_low_pct",
]

# All feature columns (for reference)
FEATURE_COLUMNS = BASE_COLUMNS + TECHNICAL_COLUMNS + VOLUME_COLUMNS + MARKET_COLUMNS

# Meta columns
META_COLUMNS = [
    "feature_version",
    "created_at",
]

ALL_COLUMNS = FEATURE_COLUMNS + META_COLUMNS

# ── DDL ───────────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {MARKET_FEATURES_TABLE} (
    timestamp              TIMESTAMPTZ      NOT NULL,
    symbol                 TEXT             NOT NULL,
    open                   DOUBLE PRECISION NOT NULL,
    high                   DOUBLE PRECISION NOT NULL,
    low                    DOUBLE PRECISION NOT NULL,
    close                  DOUBLE PRECISION NOT NULL,
    volume                 BIGINT           NOT NULL DEFAULT 0,
    ema20                  DOUBLE PRECISION,
    ema50                  DOUBLE PRECISION,
    rsi                    DOUBLE PRECISION,
    atr                    DOUBLE PRECISION,
    adx                    DOUBLE PRECISION,
    di_plus                DOUBLE PRECISION,
    di_minus               DOUBLE PRECISION,
    macd                   DOUBLE PRECISION,
    macd_signal            DOUBLE PRECISION,
    macd_hist              DOUBLE PRECISION,
    return_1m              DOUBLE PRECISION,
    return_3m              DOUBLE PRECISION,
    return_5m              DOUBLE PRECISION,
    high_low_pct           DOUBLE PRECISION,
    close_open_pct         DOUBLE PRECISION,
    body_pct               DOUBLE PRECISION,
    rolling_volatility     DOUBLE PRECISION,
    vwap                   DOUBLE PRECISION,
    vwap_dist_pct          DOUBLE PRECISION,
    volume_sma20           DOUBLE PRECISION,
    relative_volume        DOUBLE PRECISION,
    obv                    DOUBLE PRECISION,
    obv_normalized         DOUBLE PRECISION,
    log_volume             DOUBLE PRECISION,
    regime                 TEXT,
    session                TEXT,
    minutes_since_open     DOUBLE PRECISION,
    session_progress       DOUBLE PRECISION,
    day_of_week            DOUBLE PRECISION,
    gap_pct                DOUBLE PRECISION,
    gap_type               TEXT,
    opening_range_high     DOUBLE PRECISION,
    opening_range_low      DOUBLE PRECISION,
    opening_range_breakout_pct DOUBLE PRECISION,
    day_high               DOUBLE PRECISION,
    day_low                DOUBLE PRECISION,
    day_range_pct          DOUBLE PRECISION,
    dist_from_day_high_pct DOUBLE PRECISION,
    dist_from_day_low_pct  DOUBLE PRECISION,
    feature_version        INTEGER          NOT NULL DEFAULT 1,
    created_at             TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    PRIMARY KEY (timestamp, symbol)
);
"""

CREATE_INDEX_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_{MARKET_FEATURES_TABLE}_symbol_ts
    ON {MARKET_FEATURES_TABLE} (symbol, timestamp DESC);
"""

# ── Schema Migration ──────────────────────────────────────────────────────────
# The database table may have been created with an older schema.
# This migrates it to match the DDL above.

# CRITICAL: Map from Python column name → SQL type string for ALTER TABLE.
# This must exactly match the column names and types in CREATE_TABLE_SQL.
_NEW_COLUMNS_MAP = {
    # Technical derived features
    "return_1m":          "DOUBLE PRECISION",
    "return_3m":          "DOUBLE PRECISION",
    "return_5m":          "DOUBLE PRECISION",
    "high_low_pct":       "DOUBLE PRECISION",
    "close_open_pct":     "DOUBLE PRECISION",
    "body_pct":           "DOUBLE PRECISION",
    "rolling_volatility": "DOUBLE PRECISION",
    # Volume
    "log_volume":         "DOUBLE PRECISION",
    # Market context
    "minutes_since_open": "DOUBLE PRECISION",
    "session_progress":   "DOUBLE PRECISION",
    "day_of_week":        "DOUBLE PRECISION",
    "gap_pct":            "DOUBLE PRECISION",
    "gap_type":           "TEXT",
    "opening_range_high": "DOUBLE PRECISION",
    "opening_range_low":  "DOUBLE PRECISION",
    "opening_range_breakout_pct": "DOUBLE PRECISION",
    "day_high":           "DOUBLE PRECISION",
    "day_low":            "DOUBLE PRECISION",
    "day_range_pct":      "DOUBLE PRECISION",
    "dist_from_day_high_pct": "DOUBLE PRECISION",
    "dist_from_day_low_pct":  "DOUBLE PRECISION",
}


def _ensure_schema():
    """
    Idempotent schema migration: ALTER TABLE ADD COLUMN for any missing columns.
    """
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(engine)
    try:
        existing_columns = {col["name"] for col in inspector.get_columns(MARKET_FEATURES_TABLE)}
    except Exception as e:
        logger.warning(f"Schema check failed (table may not exist yet): {e}")
        return

    missing = {name: dtype for name, dtype in _NEW_COLUMNS_MAP.items() if name not in existing_columns}
    if not missing:
        return

    with engine.begin() as conn:
        for col_name, col_type in missing.items():
            sql = f'ALTER TABLE {MARKET_FEATURES_TABLE} ADD COLUMN IF NOT EXISTS "{col_name}" {col_type};'
            try:
                conn.execute(text(sql))
                logger.info(f"Migration: added column '{col_name}' ({col_type})")
            except Exception as e:
                logger.warning(f"Migration: could not add '{col_name}': {e}")

    logger.info(f"Schema migration: added {len(missing)} column(s) to '{MARKET_FEATURES_TABLE}'.")


# ── Public API ────────────────────────────────────────────────────────────────


def create_table():
    """Create the market_features table if it doesn't exist,
    then migrate to add any missing columns."""
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        conn.execute(text(CREATE_INDEX_SQL))
    logger.info(f"Table '{MARKET_FEATURES_TABLE}' ensured.")
    _ensure_schema()


def _get_table_obj():
    """
    Build a SQLAlchemy Table object that matches our ALL_COLUMNS schema.
    
    CRITICAL: This does NOT use MetaData.reflect() because the existing DB
    table may be missing newly added columns (from Feature Set v1.0).
    Instead we construct the Table object programmatically from ALL_COLUMNS,
    which ensures the INSERT statement always knows about every column.
    
    PK is (timestamp, symbol).
    """
    meta = MetaData()

    # Column type map
    def _col_type(col_name: str):
        if col_name in ("timestamp", "created_at"):
            return DateTime(timezone=True)
        if col_name in ("symbol", "regime", "session", "gap_type"):
            return String
        if col_name == "volume":
            return BigInteger
        if col_name in ("feature_version",):
            return Integer
        return Float  # default for all DOUBLE PRECISION columns

    columns = []
    for cname in ALL_COLUMNS:
        col = Column(cname, _col_type(cname), primary_key=(cname in ("timestamp", "symbol")))
        columns.append(col)

    # Also add created_at default
    for c in columns:
        if c.name == "created_at":
            c.server_default = text("NOW()")
        if c.name == "feature_version":
            c.server_default = text("1")

    table = Table(MARKET_FEATURES_TABLE, meta, *columns, extend_existing=True)
    return table


def insert_features(df: pd.DataFrame) -> int:
    """
    Insert feature rows into market_features.
    Rows with duplicate (timestamp, symbol) are ignored (ON CONFLICT DO NOTHING).
    Returns the number of rows inserted.
    """
    if df.empty:
        return 0

    # Ensure required columns exist
    missing = [c for c in BASE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Add metadata
    df = df.copy()
    if "feature_version" not in df.columns:
        df["feature_version"] = 2  # Feature Set v1.0
    if "created_at" not in df.columns:
        df["created_at"] = pd.Timestamp.now(tz="UTC")

    # Only keep known columns
    existing_cols = [c for c in ALL_COLUMNS if c in df.columns]
    to_insert = df[existing_cols].copy()

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    tbl = _get_table_obj()

    rows = to_insert.to_dict(orient="records")
    inserted = 0

    with engine.begin() as conn:
        for chunk_start in range(0, len(rows), 500):
            chunk = rows[chunk_start:chunk_start + 500]
            stmt = pg_insert(tbl).values(chunk).on_conflict_do_nothing(
                index_elements=["timestamp", "symbol"]
            )
            result = conn.execute(stmt)
            inserted += result.rowcount

    if inserted:
        logger.info(f"Inserted {inserted} feature rows into '{MARKET_FEATURES_TABLE}'.")
    return inserted


def update_features(df: pd.DataFrame) -> int:
    """
    Upsert feature rows: update non-key columns for matching (timestamp, symbol),
    insert new rows. Returns number of affected rows.
    """
    if df.empty:
        return 0

    missing = [c for c in BASE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    if "feature_version" not in df.columns:
        df["feature_version"] = 1
    if "created_at" not in df.columns:
        df["created_at"] = pd.Timestamp.now(tz="UTC")

    existing_cols = [c for c in ALL_COLUMNS if c in df.columns]
    to_upsert = df[existing_cols].copy()

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    tbl = _get_table_obj()

    # Build update dict for all columns except the PK
    pk_cols = {"timestamp", "symbol"}
    update_cols = {c.name: c for c in tbl.columns if c.name not in pk_cols}

    rows = to_upsert.to_dict(orient="records")
    affected = 0

    with engine.begin() as conn:
        for chunk_start in range(0, len(rows), 500):
            chunk = rows[chunk_start:chunk_start + 500]
            stmt = pg_insert(tbl).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["timestamp", "symbol"],
                set_={col: stmt.excluded[col] for col in update_cols},
            )
            result = conn.execute(stmt)
            affected += result.rowcount

    if affected:
        logger.info(f"Upserted {affected} feature rows into '{MARKET_FEATURES_TABLE}'.")
    return affected


def load_latest(symbol: str) -> Optional[pd.Series]:
    """
    Fetch the most recent feature row for a given symbol.
    Returns None if no data exists.
    """
    query = f"""
        SELECT * FROM {MARKET_FEATURES_TABLE}
        WHERE symbol = :symbol
        ORDER BY timestamp DESC
        LIMIT 1
    """
    df = pd.read_sql(text(query), engine, params={"symbol": symbol})
    if df.empty:
        return None
    return df.iloc[0]


def load_feature_history(symbol: str, limit: int = 500) -> pd.DataFrame:
    """
    Fetch recent feature history for a symbol.
    Returns DataFrame ordered by timestamp ascending.
    """
    query = f"""
        SELECT * FROM {MARKET_FEATURES_TABLE}
        WHERE symbol = :symbol
        ORDER BY timestamp DESC
        LIMIT :limit
    """
    df = pd.read_sql(text(query), engine, params={"symbol": symbol, "limit": limit})
    if not df.empty:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def load_feature_range(
    symbol: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    """
    Fetch feature rows for a symbol within a time range.
    Returns DataFrame ordered by timestamp ascending.
    """
    query = f"""
        SELECT * FROM {MARKET_FEATURES_TABLE}
        WHERE symbol = :symbol
          AND timestamp >= :start
          AND timestamp <= :end
        ORDER BY timestamp ASC
    """
    df = pd.read_sql(
        text(query),
        engine,
        params={"symbol": symbol, "start": start, "end": end},
    )
    return df


def delete_duplicates() -> int:
    """
    Remove duplicate rows keeping only the first occurrence per (timestamp, symbol).
    Uses a window-function approach. Returns number of rows deleted.
    """
    delete_sql = f"""
        DELETE FROM {MARKET_FEATURES_TABLE}
        WHERE ctid NOT IN (
            SELECT min(ctid)
            FROM {MARKET_FEATURES_TABLE}
            GROUP BY timestamp, symbol
        )
    """
    with engine.begin() as conn:
        result = conn.execute(text(delete_sql))
    if result.rowcount:
        logger.info(f"Deleted {result.rowcount} duplicate rows from '{MARKET_FEATURES_TABLE}'.")
    return result.rowcount


def exists(timestamp: str, symbol: str) -> bool:
    """
    Check if a feature row exists for the given timestamp and symbol.

    Args:
        timestamp: ISO-format timestamp string.
        symbol: Symbol identifier (e.g. "NIFTY-I").

    Returns:
        True if a row with that (timestamp, symbol) exists.
    """
    query = f"""
        SELECT 1 FROM {MARKET_FEATURES_TABLE}
        WHERE timestamp = :ts AND symbol = :symbol
        LIMIT 1
    """
    with engine.connect() as conn:
        result = conn.execute(
            text(query),
            {"ts": timestamp, "symbol": symbol},
        )
        return result.first() is not None


def table_exists() -> bool:
    """Check if the market_features table exists."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.tables "
                "  WHERE table_name = :name"
                ")"
            ),
            {"name": MARKET_FEATURES_TABLE},
        )
        return result.scalar()
