"""
Base Predictor Interface
─────────────────────────
Defines the contract for all predictor implementations (rule-based, ML, ensemble).

Usage:
    class XGBoostPredictor(BasePredictor):
        def predict(self, features):
            ...
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BasePredictor(ABC):
    """
    Abstract base class for all prediction engines.

    Every predictor must implement:
      - predict(features) -> PredictionResult
      - name -> str
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this predictor."""

    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> "PredictionResult":
        """
        Produce a prediction from a feature vector.

        Args:
            features: Dictionary of feature_name -> value.

        Returns:
            PredictionResult with probabilities, confidence, and reasons.
        """

    def load(self) -> bool:
        """Optional: load model from disk. Returns True if successful."""
        return True


class PredictionResult:
    """
    Structured prediction output.

    Attributes:
        bullish: Bullish probability (0-100).
        bearish: Bearish probability (0-100).
        neutral: Neutral probability (0-100).
        confidence: Confidence score (0-100).
        prediction: "bullish", "bearish", or "neutral".
        reasons: List of human-readable explanation strings.
        reason_scores: Dict of component_name -> score for structured logging.
        entry: Suggested entry price.
        stop_loss: Suggested stop-loss price.
        target: Suggested target price.
    """

    def __init__(
        self,
        bullish: float = 33.3,
        bearish: float = 33.3,
        neutral: float = 33.4,
        confidence: float = 50.0,
        prediction: str = "neutral",
        reasons: Optional[List[str]] = None,
        reason_scores: Optional[Dict[str, float]] = None,
        entry: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
    ):
        self.bullish = round(bullish, 1)
        self.bearish = round(bearish, 1)
        self.neutral = round(neutral, 1)
        self.confidence = round(confidence, 1)
        self.prediction = prediction
        self.reasons = reasons or []
        self.reason_scores = reason_scores or {}
        self.entry = entry
        self.stop_loss = stop_loss
        self.target = target

    def to_dict(self) -> dict:
        return {
            "bullish": self.bullish,
            "bearish": self.bearish,
            "neutral": self.neutral,
            "confidence": self.confidence,
            "prediction": self.prediction,
            "reasons": self.reasons,
            "reason_scores": self.reason_scores,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "target": self.target,
        }

    def __repr__(self) -> str:
        return (
            f"Prediction({self.prediction}, "
            f"bull={self.bullish}% bear={self.bearish}% "
            f"conf={self.confidence}%)"
        )
