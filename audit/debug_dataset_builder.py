"""
PHASE A — Debug: Why dataset_builder drops 100% of rows
=========================================================
Reproduces the exact pipeline and prints diagnostics.
No assumptions. No fixes.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from database.db import read_sql
from datasets.labeling import generate_labels
from utils.logger import get_logger

logger = get_logger("debug_dataset_builder")

# Exact feature list from dataset_builder.py
NUMERIC_FEATURES = [
    'open', 'high', 'low', 'close', 'volume',
    'ema20', 'ema50', 'sma20', 'sma50',
    'rsi', 'atr', 'adx', 'di_plus', 'di_minus',
    'macd', 'macd_signal', 'macd_hist',
    'vwap', 'vwap_dist_pct',
    'volume_sma20', 'relative_volume', 'obv', 'obv_normalized',
]
CATEGORICAL_FEATURES = ['regime', 'session']

SEP = "-" * 70


def step(label, val):
    print(f"\n{SEP}")
    print(f"  {label}")
    print(SEP)
    print(val)


def main():
    # 1. Load raw data
    df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
    step("1. Original shape", f"{df.shape[0]} rows x {df.shape[1]} cols")

    # 2. Check features exist
    available = [c for c in NUMERIC_FEATURES if c in df.columns]
    missing = [c for c in NUMERIC_FEATURES if c not in df.columns]
    step("2. Available features", f"Available ({len(available)}): {available}\nMissing ({len(missing)}): {missing}")

    # 3. NaN counts BEFORE labeling
    nan_before = {c: int(df[c].isna().sum()) for c in available}
    total_nan = sum(nan_before.values())
    step("3. NaN count BEFORE labeling", f"Total NaN: {total_nan}\nPer feature: {nan_before}")

    # 4. Infinity counts
    inf_before = {}
    for c in available:
        s = df[c]
        inf_before[c] = int(np.isinf(s.dropna()).sum()) if s.dtype.kind in ('f', 'i') else 0
    step("4. Infinity count BEFORE labeling", inf_before)

    # 5. Index type before labeling
    step("5. Index info BEFORE labeling",
         f"type={type(df.index)}, dtype={df.index.dtype}, "
         f"is_unique={df.index.is_unique}, range={df.index[0]}..{df.index[-1]}")

    # 6. generate_labels
    lbl = generate_labels(df.copy(), horizon_minutes=10)
    step("6. After generate_labels", f"Shape: {lbl.shape}")
    step("6a. Index type AFTER labeling",
         f"type={type(lbl.index)}, dtype={lbl.index.dtype}, "
         f"is_unique={lbl.index.is_unique}, range={lbl.index[0]}..{lbl.index[-1]}")

    # 7. Check that forward_return_pct is NOT in feature_cols
    step("7. Columns that would be mistaken as features",
         [c for c in NUMERIC_FEATURES + ['label', 'forward_return_pct']
          if c not in NUMERIC_FEATURES and c in lbl.columns])

    # 8. NaN counts AFTER labeling (features only)
    nan_after = {c: int(lbl[c].isna().sum()) for c in available}
    step("8. NaN count AFTER labeling (features only)", nan_after)

    # 9. One-hot encode
    regime_dummies = pd.get_dummies(lbl['regime'], prefix='regime')
    session_dummies = pd.get_dummies(lbl['session'], prefix='session')
    step("9a. One-hot regime shape", str(regime_dummies.shape))
    step("9b. One-hot session shape", str(session_dummies.shape))
    step("9c. One-hot dtypes",
         f"regime: {regime_dummies.dtypes.unique()}, session: {session_dummies.dtypes.unique()}")

    # 10. Concat
    lbl2 = pd.concat([lbl, regime_dummies, session_dummies], axis=1)
    step("10. After pd.concat", f"Shape: {lbl2.shape}, Index is_unique: {lbl2.index.is_unique}")

    # Check for duplicate columns
    dup_cols = lbl2.columns[lbl2.columns.duplicated()].tolist()
    step("10a. Duplicate column names", dup_cols if dup_cols else "None")

    # 11. Build feature list with dummies
    available_with_dummies = available + list(regime_dummies.columns) + list(session_dummies.columns)
    available_with_dummies_final = [c for c in available_with_dummies if c in lbl2.columns]

    # 12. NaN in dummies
    dummy_nan = {}
    for c in list(regime_dummies.columns) + list(session_dummies.columns):
        n = int(lbl2[c].isna().sum())
        if n > 0:
            dummy_nan[c] = n
    step("12. NaN in dummy columns", dummy_nan if dummy_nan else "None (all 0)")

    # 13. Construct the feature-only DataFrame (exactly as build_dataset does)
    feature_only = lbl2[available_with_dummies_final]
    step("13. Feature-only DataFrame", f"Shape: {feature_only.shape}")

    # 14. Check rows where ANY feature is NaN
    any_nan = feature_only.isna().any(axis=1).sum()
    all_nan = feature_only.isna().all(axis=1).sum()
    step("14. NaN row counts",
         f"Rows with ANY NaN: {any_nan} / {len(feature_only)} ({any_nan/len(feature_only)*100:.1f}%)\n"
         f"Rows with ALL NaN: {all_nan} / {len(feature_only)} ({all_nan/len(feature_only)*100:.1f}%)")

    # 15. Show first 10 NaN rows
    nan_rows = feature_only[feature_only.isna().any(axis=1)].head(10)
    step("15. First 10 rows containing NaN", nan_rows.to_string())

    # 16. Check specifically: ADX, RSI, ATR, DI_plus, DI_minus
    for c in ['adx', 'rsi', 'atr', 'di_plus', 'di_minus']:
        if c in feature_only.columns:
            n = int(feature_only[c].isna().sum())
            first_nan_idx = feature_only[c].isna().argmax()
            step(f"16. NaN check: {c}",
                 f"Total NaN: {n}\nFirst NaN at row: {first_nan_idx}")

    # 17. Double-check forward_return_pct inclusion
    step("17. Columns containing 'forward' or 'label'",
         [c for c in feature_only.columns if 'forward' in c or 'label' in c])

    # 18. Print dtypes of all columns
    step("18. Feature dtypes",
         feature_only.dtypes.to_string())

    # 19. Bool columns specifically
    bool_cols = feature_only.select_dtypes(include=['bool']).columns.tolist()
    step("19. Bool columns", bool_cols if bool_cols else "None")

    # 20. Range of timestamp values (sanity check)
    if 'timestamp' in lbl2.columns:
        ts = pd.to_datetime(lbl2['timestamp'])
        step("20. Timestamp range", f"{ts.min()} -> {ts.max()}")


if __name__ == "__main__":
    main()
