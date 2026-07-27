"""
Prediction Store
────────────────
CRUD operations for the prediction_history table.

Persists every prediction made by the prediction engine so that:
  1. The dashboard can display prediction history.
  2. Outcome data can be collected automatically for later model training.
  3. We can analyze which rules/features lead to correct vs incorrect predictions.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text

from database.db import engine
from utils.logger import get_logger

logger = get_logger("prediction_store")

PREDICTION_TABLE = "prediction_history"


# ── DDL ───────────────────────────────────────────────────────────────────────


CREATE_PREDICTION_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {PREDICTION_TABLE} (
    id                   SERIAL          PRIMARY KEY,
    timestamp            TIMESTAMPTZ     NOT NULL,
    symbol               TEXT            NOT NULL,
    prediction_time      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    time_horizon         TEXT            NOT NULL DEFAULT '1m',
    bullish_probability  DOUBLE PRECISION NOT NULL,
    bearish_probability  DOUBLE PRECISION NOT NULL,
    neutral_probability  DOUBLE PRECISION NOT NULL,
    confidence           DOUBLE PRECISION NOT NULL,
    prediction           TEXT            NOT NULL,
    entry_price          DOUBLE PRECISION NOT NULL,
    reason_json          JSONB,
    price_at_prediction  DOUBLE PRECISION NOT NULL,
    price_after_5m       DOUBLE PRECISION,
    price_after_10m      DOUBLE PRECISION,
    price_after_15m      DOUBLE PRECISION,
    actual_direction     TEXT,
    correct              BOOLEAN,
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
"""

CREATE_PREDICTION_INDEX_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_{PREDICTION_TABLE}_ts
    ON {PREDICTION_TABLE} (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_{PREDICTION_TABLE}_symbol
    ON {PREDICTION_TABLE} (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_{PREDICTION_TABLE}_correct
    ON {PREDICTION_TABLE} (correct, timestamp DESC);
"""


def ensure_table():
    """Create the prediction_history table if it doesn't exist."""
    with engine.begin() as conn:
        conn.execute(text(CREATE_PREDICTION_TABLE_SQL))
        for stmt in CREATE_PREDICTION_INDEX_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    logger.info(f"Table '{PREDICTION_TABLE}' ensured.")


# ── Insert ────────────────────────────────────────────────────────────────────


def save_prediction(
    timestamp: datetime,
    symbol: str,
    bullish_prob: float,
    bearish_prob: float,
    neutral_prob: float,
    confidence: float,
    prediction: str,
    entry_price: float,
    reasons: Optional[Dict[str, Any]] = None,
    price_at_prediction: Optional[float] = None,
    time_horizon: str = "1m",
) -> int:
    """
    Insert a prediction record into prediction_history.

    Args:
        timestamp: The candle timestamp this prediction was made for.
        symbol: Symbol identifier.
        bullish_prob: Bullish probability (0-100).
        bearish_prob: Bearish probability (0-100).
        neutral_prob: Neutral probability (0-100).
        confidence: Confidence score (0-100).
        prediction: "bullish", "bearish", or "neutral".
        entry_price: Entry price used.
        reasons: Dict of reason scores (e.g. {"ema": 20, "macd": 15}).
        price_at_prediction: The price when prediction was made (usually close).
        time_horizon: Prediction timeframe.

    Returns:
        The ID of the inserted row.
    """
    import json

    reasons_json = json.dumps(reasons) if reasons else "{}"

    sql = f"""
        INSERT INTO {PREDICTION_TABLE}
            (timestamp, symbol, prediction_time, time_horizon,
             bullish_probability, bearish_probability, neutral_probability,
             confidence, prediction, entry_price, reason_json,
             price_at_prediction)
        VALUES
            (:ts, :sym, NOW(), :horizon,
             :bull, :bear, :neut,
             :conf, :pred, :entry, CAST(:reasons AS jsonb),
             :price)
        RETURNING id
    """

    with engine.begin() as conn:
        result = conn.execute(
            text(sql),
            {
                "ts": timestamp,
                "sym": symbol,
                "horizon": time_horizon,
                "bull": round(bullish_prob, 2),
                "bear": round(bearish_prob, 2),
                "neut": round(neutral_prob, 2),
                "conf": round(confidence, 2),
                "pred": prediction,
                "entry": round(entry_price, 2),
                "reasons": reasons_json,
                "price": round(price_at_prediction, 2) if price_at_prediction else round(entry_price, 2),
            },
        )
        pred_id = result.fetchone()[0]

    logger.info(
        f"Prediction #{pred_id} saved: {prediction.upper()} "
        f"(bull={bullish_prob:.0f}% bear={bearish_prob:.0f}% "
        f"conf={confidence:.0f}%)"
    )
    return pred_id


# ── Outcome Update ────────────────────────────────────────────────────────────


def update_outcome(
    prediction_id: int,
    price_after_5m: Optional[float] = None,
    price_after_10m: Optional[float] = None,
    price_after_15m: Optional[float] = None,
):
    """
    Update a prediction with actual price outcomes.

    Args:
        prediction_id: The ID of the prediction to update.
        price_after_5m: Actual price 5 minutes after prediction.
        price_after_10m: Actual price 10 minutes after prediction.
        price_after_15m: Actual price 15 minutes after prediction.
    """
    updates = []
    params: Dict[str, Any] = {"id": prediction_id}

    if price_after_5m is not None:
        updates.append("price_after_5m = :p5")
        params["p5"] = round(price_after_5m, 2)
    if price_after_10m is not None:
        updates.append("price_after_10m = :p10")
        params["p10"] = round(price_after_10m, 2)
    if price_after_15m is not None:
        updates.append("price_after_15m = :p15")
        params["p15"] = round(price_after_15m, 2)

    if not updates:
        return False

    sql = f"""
        UPDATE {PREDICTION_TABLE}
        SET {', '.join(updates)}
        WHERE id = :id
    """
    with engine.begin() as conn:
        result = conn.execute(text(sql), params)

    return result.rowcount > 0


def mark_correctness(prediction_id: int):
    """
    Evaluate whether a prediction was correct based on its actual outcomes.
    Sets the 'correct' and 'actual_direction' columns.

    Rules:
      - correct = True if prediction direction matches actual price movement
      - For 5m window: if close > entry, direction is 'up', etc.
    """
    sql = f"""
        SELECT * FROM {PREDICTION_TABLE}
        WHERE id = :id
    """
    df = pd.read_sql(text(sql), engine, params={"id": prediction_id})
    if df.empty:
        return

    row = df.iloc[0]
    entry = row["price_at_prediction"]
    pred = row["prediction"]
    price_5m = row.get("price_after_5m")

    if entry is None or entry == 0 or price_5m is None:
        return

    actual_move = price_5m - entry
    if actual_move > 0:
        actual_direction = "up"
        correct = pred == "bullish"
    elif actual_move < 0:
        actual_direction = "down"
        correct = pred == "bearish"
    else:
        actual_direction = "flat"
        correct = pred == "neutral"

    sql = f"""
        UPDATE {PREDICTION_TABLE}
        SET actual_direction = :dir, correct = :cor
        WHERE id = :id
    """
    with engine.begin() as conn:
        conn.execute(
            text(sql),
            {"dir": actual_direction, "cor": correct, "id": prediction_id},
        )


def update_outcome_and_mark(
    prediction_id: int,
    price_after_5m: Optional[float] = None,
    price_after_10m: Optional[float] = None,
    price_after_15m: Optional[float] = None,
):
    """Convenience: update prices then evaluate correctness."""
    update_outcome(prediction_id, price_after_5m, price_after_10m, price_after_15m)
    mark_correctness(prediction_id)


# ── Query ─────────────────────────────────────────────────────────────────────


def get_recent(
    symbol: str,
    limit: int = 50,
    only_correctness_known: bool = False,
) -> List[Dict]:
    """
    Fetch recent predictions for a symbol.

    Args:
        symbol: Symbol to filter by.
        limit: Maximum number of predictions to return.
        only_correctness_known: If True, only return predictions that have
                                been evaluated (correct column is not null).

    Returns:
        List of prediction dicts.
    """
    where = "symbol = :symbol"
    if only_correctness_known:
        where += " AND correct IS NOT NULL"

    sql = f"""
        SELECT * FROM {PREDICTION_TABLE}
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT :limit
    """
    df = pd.read_sql(
        text(sql), engine,
        params={"symbol": symbol, "limit": limit},
    )
    if df.empty:
        return []

    # Convert timestamps to ISO strings for JSON serialization
    df["timestamp"] = df["timestamp"].astype(str)
    df["prediction_time"] = df["prediction_time"].astype(str)
    df["created_at"] = df["created_at"].astype(str)

    return df.to_dict(orient="records")


def get_pending_outcomes(limit: int = 100) -> List[Dict]:
    """
    Fetch predictions that haven't been evaluated yet
    (price_after_5m IS NULL) but were made at least 6 minutes ago.

    Returns:
        List of prediction dicts ready for outcome evaluation.
    """
    sql = f"""
        SELECT * FROM {PREDICTION_TABLE}
        WHERE price_after_5m IS NULL
          AND prediction_time < NOW() - INTERVAL '6 minutes'
        ORDER BY prediction_time ASC
        LIMIT :limit
    """
    df = pd.read_sql(text(sql), engine, params={"limit": limit})
    if df.empty:
        return []

    df["timestamp"] = df["timestamp"].astype(str)
    df["prediction_time"] = df["prediction_time"].astype(str)
    df["created_at"] = df["created_at"].astype(str)

    return df.to_dict(orient="records")


def get_statistics(symbol: str) -> Dict:
    """
    Return summary statistics for predictions on a given symbol.

    Args:
        symbol: Symbol to analyze.

    Returns:
        Dict with accuracy, total predictions, win/loss counts, avg confidence.
    """
    sql = f"""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE correct = TRUE) as correct_count,
            COUNT(*) FILTER (WHERE correct = FALSE) as incorrect_count,
            COUNT(*) FILTER (WHERE correct IS NULL) as pending_count,
            AVG(confidence) FILTER (WHERE correct IS NOT NULL) as avg_confidence,
            AVG(bullish_probability) as avg_bullish,
            AVG(bearish_probability) as avg_bearish,
            AVG(neutral_probability) as avg_neutral
        FROM {PREDICTION_TABLE}
        WHERE symbol = :symbol
    """
    df = pd.read_sql(text(sql), engine, params={"symbol": symbol})
    if df.empty:
        return {}

    row = df.iloc[0]
    total = int(row["total"] or 0)
    correct = int(row["correct_count"] or 0)
    evaluated = correct + int(row["incorrect_count"] or 0)

    return {
        "symbol": symbol,
        "total_predictions": total,
        "evaluated": evaluated,
        "correct": correct,
        "incorrect": int(row["incorrect_count"] or 0),
        "pending": int(row["pending_count"] or 0),
        "accuracy": round(correct / evaluated * 100, 1) if evaluated > 0 else None,
        "avg_confidence": round(float(row["avg_confidence"] or 0), 1),
        "avg_bullish": round(float(row["avg_bullish"] or 0), 1),
        "avg_bearish": round(float(row["avg_bearish"] or 0), 1),
        "avg_neutral": round(float(row["avg_neutral"] or 0), 1),
    }
