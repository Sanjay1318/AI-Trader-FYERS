"""
Scoring Engine
──────────────
Aggregates individual rule evaluations into a composite score.

Takes the output of individual rules and combines them into
bullish, bearish, and total scores that can be normalized
into probabilities.
"""

from typing import Dict, List, Optional, Tuple

from inference.rules import Rule


class ScoreResult:
    """Result of scoring a feature vector against all rules."""

    def __init__(
        self,
        total_score: float = 0.0,
        max_possible: float = 100.0,
        bullish_score: float = 0.0,
        bearish_score: float = 0.0,
        reasons: Optional[List[str]] = None,
        reason_scores: Optional[Dict[str, float]] = None,
    ):
        self.total_score = total_score
        self.max_possible = max_possible
        self.bullish_score = bullish_score
        self.bearish_score = bearish_score
        self.reasons = reasons or []
        self.reason_scores = reason_scores or {}


class ScoringEngine:
    """
    Evaluates all rules against a feature vector and produces a composite score.

    Usage:
        engine = ScoringEngine()
        result = engine.score(features)
        print(result.bullish_score, result.bearish_score, result.reasons)
    """

    def __init__(self, rules: Optional[List[Rule]] = None):
        self.rules = rules or self._default_rules()
        self._max_possible = sum(abs(r.weight) for r in self.rules)

    @staticmethod
    def _default_rules() -> List[Rule]:
        from inference.rules import get_default_rules
        return get_default_rules()

    def score(self, features: Dict) -> ScoreResult:
        """
        Evaluate all rules against a feature dict.

        Args:
            features: Dict of feature_name -> value (e.g. from a DataFrame row).

        Returns:
            ScoreResult with total, bullish, bearish scores, reasons, and reason_scores.
        """
        total = 0.0
        bullish = 0.0
        bearish = 0.0
        reasons: List[str] = []
        reason_scores: Dict[str, float] = {}

        for rule in self.rules:
            try:
                score, reason = rule.evaluate(features)
            except Exception as e:
                score, reason = 0.0, None

            total += abs(score)
            if score > 0:
                bullish += score
            elif score < 0:
                bearish += abs(score)

            if score != 0:
                reason_scores[rule.name] = round(score, 1)

            if reason:
                reasons.append(reason)

        return ScoreResult(
            total_score=total,
            max_possible=self._max_possible,
            bullish_score=bullish,
            bearish_score=bearish,
            reasons=reasons,
            reason_scores=reason_scores,
        )
