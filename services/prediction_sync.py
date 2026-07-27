"""
Prediction Sync Service
────────────────────────
Thin orchestrator that generates predictions from the latest feature vectors
and persists them to prediction_history.

Called automatically after FeatureSync completes. Keeps the architecture clean:
  Collector → FeatureSync → PredictionSync

Delegates to:
  1. RulePredictor — generate prediction from features
  2. PredictionStore — persist to prediction_history
"""

from typing import Optional

import pandas as pd

from inference.predictor import RulePredictor
from inference.base_predictor import BasePredictor, PredictionResult
from inference.prediction_store import (
    ensure_table,
    save_prediction,
    get_recent,
    get_statistics,
)
from utils.logger import get_logger

logger = get_logger("prediction_sync")


class PredictionSyncService:
    """
    Generates predictions from market_features and persists them.

    Usage:
        psync = PredictionSyncService()
        psync.sync_latest("NIFTY-I")
        psync.sync_features(feature_row)
    """

    def __init__(self, predictor: Optional[BasePredictor] = None):
        self.predictor = predictor or RulePredictor()
        self._table_ensured = False

    def ensure_storage(self):
        if not self._table_ensured:
            ensure_table()
            self._table_ensured = True

    def sync_features(self, feature_row: dict) -> Optional[int]:
        """
        Generate a prediction from a single feature vector and persist it.

        Args:
            feature_row: Dict of feature_name -> value
                         (usually the latest row from market_features).

        Returns:
            prediction_history row ID, or None if features were insufficient.
        """
        # Ensure required fields exist
        if not feature_row or "close" not in feature_row:
            logger.warning("PredictionSync: insufficient features (missing close)")
            return None

        # Generate prediction
        try:
            result: PredictionResult = self.predictor.predict(feature_row)
        except Exception as e:
            logger.error(f"PredictionSync: prediction failed: {e}")
            return None

        # Extract metadata from feature row
        timestamp = feature_row.get("timestamp")
        symbol = feature_row.get("symbol", "NIFTY-I")
        entry_price = result.entry or feature_row.get("close", 0)
        price_at_pred = feature_row.get("close", entry_price)

        # Persist
        self.ensure_storage()
        try:
            pred_id = save_prediction(
                timestamp=timestamp,
                symbol=symbol,
                bullish_prob=result.bullish,
                bearish_prob=result.bearish,
                neutral_prob=result.neutral,
                confidence=result.confidence,
                prediction=result.prediction,
                entry_price=entry_price,
                reasons=result.reason_scores,
                price_at_prediction=price_at_pred,
                time_horizon="1m",
            )
            logger.info(
                f"PredictionSync: #{pred_id} — {result.prediction.upper()} "
                f"(bull={result.bullish:.0f}% bear={result.bearish:.0f}% "
                f"conf={result.confidence:.0f}%)"
            )
            return pred_id
        except Exception as e:
            logger.error(f"PredictionSync: persistence failed: {e}")
            return None

    def sync_latest(self, symbol: str = "NIFTY-I") -> Optional[int]:
        """
        Fetch the latest feature row from market_features and generate a prediction.

        Args:
            symbol: Symbol to predict.

        Returns:
            prediction_history row ID, or None.
        """
        from sqlalchemy import text
        from database.db import engine

        query = text("""
            SELECT * FROM market_features
            WHERE symbol = :symbol
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        df = pd.read_sql(query, engine, params={"symbol": symbol})
        if df.empty:
            logger.warning(f"PredictionSync: no features found for {symbol}")
            return None

        return self.sync_features(df.iloc[0].to_dict())

    def get_latest_prediction(self, symbol: str = "NIFTY-I") -> Optional[dict]:
        """Return the most recent prediction result (without re-running)."""
        recent = get_recent(symbol, limit=1)
        return recent[0] if recent else None

    def get_statistics(self, symbol: str = "NIFTY-I") -> dict:
        """Return prediction performance statistics."""
        return get_statistics(symbol)
