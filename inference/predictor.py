"""
Rule-Based Predictor
────────────────────
Public API for the rule-based prediction engine.

Implements the BasePredictor interface so it can be swapped later
with ML-based predictors without changing callers.

Flow:
  features → rules → scoring → probability → PredictionResult
"""

from typing import Any, Dict, List, Optional

from inference.base_predictor import BasePredictor, PredictionResult
from inference.scoring import ScoringEngine
from inference.probability import (
    scores_to_probabilities,
    compute_entry_sl_target,
)


class RulePredictor(BasePredictor):
    """
    Rule-based market predictor using technical indicators.

    Uses a set of weighted rules (EMA crossover, RSI, MACD, VWAP, volume,
    regime, ADX, session, ATR) to produce bullish/bearish/neutral
    probabilities with confidence and explanations.

    Can be replaced with XGBoostPredictor(BasePredictor) later.
    """

    def __init__(self, rules: Optional[List] = None):
        self.scoring_engine = ScoringEngine(rules=rules)

    @property
    def name(self) -> str:
        return "rule_based_v1"

    def predict(self, features: Dict[str, Any]) -> PredictionResult:
        """
        Produce a prediction from a feature dictionary.

        Args:
            features: Feature-name → value dictionary.
                      Usually the latest row from market_features.

        Returns:
            PredictionResult with probabilities, confidence, reasons,
            entry/sl/target levels.
        """
        score_result = self.scoring_engine.score(features)
        probs = scores_to_probabilities(score_result)
        entry, sl, target = compute_entry_sl_target(features)

        return PredictionResult(
            bullish=probs["bullish"],
            bearish=probs["bearish"],
            neutral=probs["neutral"],
            confidence=probs["confidence"],
            prediction=probs["prediction"],
            reasons=score_result.reasons,
            reason_scores=score_result.reason_scores,
            entry=entry,
            stop_loss=sl,
            target=target,
        )


# ── Convenience function ──────────────────────────────────────────────────────


def predict_from_features(features: Dict[str, Any]) -> PredictionResult:
    """One-shot convenience: create a predictor and predict."""
    predictor = RulePredictor()
    return predictor.predict(features)
