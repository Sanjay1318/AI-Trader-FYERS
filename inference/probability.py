"""
Probability Converter
──────────────────────
Converts raw scores from the ScoringEngine into normalized probabilities
(bullish, bearish, neutral) with a confidence metric.

This is the component that can be swapped later for:
  - XGBoost softmax output
  - LightGBM probability calibration
  - Ensemble weighted average
"""

from typing import Dict, List, Optional, Tuple

from inference.scoring import ScoreResult


MAX_CONFIDENCE_RANGE = 100.0


def scores_to_probabilities(
    score_result: ScoreResult,
) -> Dict[str, float]:
    """
    Convert raw scores into normalized probabilities.

    The conversion works as follows:
      - bull_pct = bullish_score / max_possible * 100
      - bear_pct = bearish_score / max_possible * 100
      - neutral_pct = 100 - bull_pct - bear_pct (clamped to [0, 100])
      - confidence = total_score / max_possible * 100

    Args:
        score_result: Output from ScoringEngine.score().

    Returns:
        Dict with keys: bullish, bearish, neutral, confidence, prediction.
    """
    max_pos = score_result.max_possible
    if max_pos <= 0:
        return {
            "bullish": 33.3,
            "bearish": 33.3,
            "neutral": 33.4,
            "confidence": 0.0,
            "prediction": "neutral",
        }

    raw_bull = (score_result.bullish_score / max_pos) * 100.0
    raw_bear = (score_result.bearish_score / max_pos) * 100.0

    # Clamp individually
    bull_pct = min(max(raw_bull, 0.0), 100.0)
    bear_pct = min(max(raw_bear, 0.0), 100.0)

    # Neutral = leftover, clamped
    neutral_pct = max(100.0 - bull_pct - bear_pct, 0.0)

    # Re-scale so they sum to 100
    total_pct = bull_pct + bear_pct + neutral_pct
    if total_pct > 0:
        bull_pct = bull_pct / total_pct * 100.0
        bear_pct = bear_pct / total_pct * 100.0
        neutral_pct = neutral_pct / total_pct * 100.0

    # Confidence = how much of the max score was activated
    confidence = (score_result.total_score / max_pos) * 100.0
    confidence = min(max(confidence, 0.0), 100.0)

    # Prediction label
    if bull_pct > bear_pct and bull_pct > neutral_pct:
        prediction = "bullish"
    elif bear_pct > bull_pct and bear_pct > neutral_pct:
        prediction = "bearish"
    else:
        prediction = "neutral"

    return {
        "bullish": round(bull_pct, 1),
        "bearish": round(bear_pct, 1),
        "neutral": round(neutral_pct, 1),
        "confidence": round(confidence, 1),
        "prediction": prediction,
    }


def compute_entry_sl_target(
    features: Dict,
    atr_multiplier_sl: float = 1.5,
    atr_multiplier_target: float = 2.0,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute suggested entry, stop-loss, and target prices based on current
    price and ATR.

    Args:
        features: Feature dict (must include 'close' and optionally 'atr').
        atr_multiplier_sl: Multiplier for ATR to set stop distance.
        atr_multiplier_target: Multiplier for ATR to set target distance.

    Returns:
        (entry, stop_loss, target) or (None, None, None) if price unavailable.
    """
    close = features.get("close")
    atr = features.get("atr")

    if close is None:
        return None, None, None

    entry = close

    if atr is not None and atr > 0:
        sl_distance = atr * atr_multiplier_sl
        target_distance = atr * atr_multiplier_target
        stop_loss = round(close - sl_distance, 1)
        target = round(close + target_distance, 1)
    else:
        # Fallback: use 0.5% of price
        pct = close * 0.005
        stop_loss = round(close - pct, 1)
        target = round(close + pct * 2, 1)

    return entry, stop_loss, target
