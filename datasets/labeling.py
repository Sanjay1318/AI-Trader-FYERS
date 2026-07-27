"""
Label Generation for Supervised ML Training
=============================================
Generates 3-class labels (UP/DOWN/NEUTRAL) from forward returns.

Uses percentile-based thresholds (P33/P67) rather than arbitrary values.
Thresholds are data-driven and MUST be computed from TRAINING DATA ONLY
to prevent data leakage.

CRITICAL RULES:
  1. compute_thresholds() must receive ONLY training data.
  2. generate_labels() can receive precomputed/frozen thresholds.
  3. Validation and test sets use the SAME frozen thresholds.
  4. Labels are generated independently WITHIN EACH IST TRADING SESSION.
     A candle at timestamp T looks for its target at T + horizon_minutes
     within the SAME IST trading date. If no such target exists (end of
     day), the row is dropped. No cross-session labels are ever created.
"""

import numpy as np
import pandas as pd
from utils.logger import get_logger

logger = get_logger("labeling")

# Default fallback thresholds (used only when train data is insufficient)
_DEFAULT_THRESHOLDS = {
    5: {"up": 0.05, "down": -0.05},
    10: {"up": 0.07, "down": -0.07},
    15: {"up": 0.09, "down": -0.09},
}


def _to_ist_date(ts_series):
    """Convert a Series of timestamps to IST date for session grouping."""
    try:
        return ts_series.dt.tz_convert('Asia/Kolkata').dt.date
    except TypeError:
        return ts_series.dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata').dt.date


def compute_thresholds(
    df: pd.DataFrame,
    horizon_minutes: int = 10,
    up_percentile: float = 67.0,
    down_percentile: float = 33.0,
) -> dict:
    """
    Compute data-driven UP/DOWN thresholds from forward return distribution.

    IMPORTANT: This function MUST receive TRAINING DATA ONLY.
    Validation and test data must NEVER influence threshold selection.

    Args:
        df: DataFrame with 'timestamp' and 'close' columns, ordered chronologically.
            Should contain ONLY training data.
        horizon_minutes: Forward-looking window in minutes.
        up_percentile: Percentile for UP threshold (default 67 = top third).
        down_percentile: Percentile for DOWN threshold (default 33 = bottom third).

    Returns:
        dict with 'up', 'down', 'symmetric' thresholds as percentages.
    """
    timestamps = pd.to_datetime(df['timestamp'])
    closes = df['close'].values
    n = len(closes)

    forward_rets = []
    ist_dates = _to_ist_date(timestamps)

    for i in range(n):
        target_ts = timestamps[i] + pd.Timedelta(minutes=horizon_minutes)
        target_idx = None
        current_ist_date = ist_dates[i]

        for j in range(i + 1, min(i + horizon_minutes + 5, n)):
            if ist_dates[j] != current_ist_date:
                break
            if timestamps[j] >= target_ts:
                target_idx = j
                break

        if target_idx is not None and closes[i] > 0:
            ret = (closes[target_idx] - closes[i]) / closes[i] * 100.0
            forward_rets.append(ret)

    if len(forward_rets) < 100:
        logger.warning(
            f"Only {len(forward_rets)} valid forward returns for {horizon_minutes}m "
            f"threshold computation — using fallback defaults"
        )
        return _DEFAULT_THRESHOLDS.get(horizon_minutes, {"up": 0.05, "down": -0.05})

    arr = np.array(forward_rets)
    up_thresh = float(np.percentile(arr, up_percentile))
    down_thresh = float(np.percentile(arr, down_percentile))
    symmetric = float(np.median(np.abs(arr)))

    logger.info(
        f"Thresholds for {horizon_minutes}m: UP>{up_thresh:.4f}% DOWN<{down_thresh:.4f}% "
        f"(symmetric: |r|>{symmetric:.4f}%) — computed from {len(arr)} samples"
    )
    return {
        "up": round(up_thresh, 4),
        "down": round(down_thresh, 4),
        "symmetric": round(symmetric, 4),
        "n_samples": len(arr),
    }


def generate_labels(
    df: pd.DataFrame,
    horizon_minutes: int = 10,
    thresholds: dict = None,
) -> pd.DataFrame:
    """
    Generate UP/DOWN/NEUTRAL labels for each row based on forward return.

    CRITICAL: Labels are generated independently WITHIN EACH IST TRADING SESSION.
    A candle at timestamp T looks for its target at T + horizon_minutes within
    the SAME IST trading date. If no such target exists (end of day), the row
    is dropped. No cross-session labels are ever created.

    Thresholds must be precomputed from TRAINING DATA ONLY using
    compute_thresholds(). If thresholds is None, they will be computed
    from the provided data — ONLY use this for exploration/debugging,
    never for final dataset construction.

    Args:
        df: DataFrame with 'timestamp' and 'close' columns, ordered chronologically.
        horizon_minutes: Look-ahead window.
        thresholds: dict with 'up' and 'down' values (precomputed from train).
            If None, computes from df (WARNING: potential leakage).

    Returns:
        DataFrame with original columns plus:
          - forward_return_pct: The actual forward return percentage.
          - label: 'UP', 'DOWN', or 'NEUTRAL'.
    """
    if thresholds is None:
        logger.warning(
            "No thresholds provided — computing from input data. "
            "This may cause data leakage if called on non-training data!"
        )
        thresholds = compute_thresholds(df, horizon_minutes)

    df = df.copy()
    timestamps = pd.to_datetime(df['timestamp'])
    closes = df['close'].values
    n = len(timestamps)

    # Determine IST trading dates for session-safe labeling
    ist_dates = _to_ist_date(timestamps)

    labels = []
    forward_rets = []

    for i in range(n):
        target_ts = timestamps[i] + pd.Timedelta(minutes=horizon_minutes)
        target_idx = None
        current_ist_date = ist_dates[i]

        # Only search within the same IST trading date
        for j in range(i + 1, min(i + horizon_minutes + 5, n)):
            if ist_dates[j] != current_ist_date:
                break
            if timestamps[j] >= target_ts:
                target_idx = j
                break

        if target_idx is not None and closes[i] > 0:
            ret = (closes[target_idx] - closes[i]) / closes[i] * 100.0
            forward_rets.append(ret)
            if ret > thresholds["up"]:
                labels.append("UP")
            elif ret < thresholds["down"]:
                labels.append("DOWN")
            else:
                labels.append("NEUTRAL")
        else:
            forward_rets.append(np.nan)
            labels.append(None)

    df["forward_return_pct"] = forward_rets
    df["label"] = labels

    # Drop rows where label could not be computed (end of day)
    df = df.dropna(subset=["label"])

    valid = len(df)
    counts = df["label"].value_counts()
    logger.info(
        f"Labels for {horizon_minutes}m: {valid} rows - "
        f"UP={counts.get('UP', 0)} DOWN={counts.get('DOWN', 0)} "
        f"NEUTRAL={counts.get('NEUTRAL', 0)}"
    )
    return df


def generate_multi_horizon_labels(
    df: pd.DataFrame,
    horizons: list = None,
    thresholds_map: dict = None,
) -> dict:
    """
    Generate labels for multiple horizons with per-horizon thresholds.

    Args:
        df: DataFrame with 'timestamp' and 'close'.
        horizons: List of horizon minutes. Default [5, 10, 15].
        thresholds_map: dict of {horizon: {up, down}}. If None, computed
            per-horizon (WARNING: potential leakage).

    Returns:
        dict of {horizon: labeled_DataFrame}.
    """
    if horizons is None:
        horizons = [5, 10, 15]
    if thresholds_map is None:
        thresholds_map = {}

    results = {}
    for h in horizons:
        thresh = thresholds_map.get(h)
        results[h] = generate_labels(df, horizon_minutes=h, thresholds=thresh)
    return results


def label_distribution(df_labeled: pd.DataFrame) -> dict:
    """Return class balance statistics for a labeled DataFrame."""
    if "label" not in df_labeled.columns:
        return {"error": "No 'label' column found"}

    counts = df_labeled["label"].value_counts()
    total = len(df_labeled)
    return {
        "total": total,
        "up": int(counts.get("UP", 0)),
        "down": int(counts.get("DOWN", 0)),
        "neutral": int(counts.get("NEUTRAL", 0)),
        "up_pct": round(float(counts.get("UP", 0) / total * 100), 2) if total > 0 else 0,
        "down_pct": round(float(counts.get("DOWN", 0) / total * 100), 2) if total > 0 else 0,
        "neutral_pct": round(float(counts.get("NEUTRAL", 0) / total * 100), 2) if total > 0 else 0,
    }
