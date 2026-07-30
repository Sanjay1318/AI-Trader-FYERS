"""
Dataset Builder
================
Assembles ML training datasets from market_features with labels.

Pipeline:
  1. Load market_features from DB
  2. Auto-exclude features that are 100% NaN (pipeline computation failures)
  3. Feature selection (drop meta columns, categorical encoding)
  4. Join labels (forward returns + UP/DOWN/NEUTRAL) using TRAIN-ONLY thresholds
  5. Remove warmup rows (NaN from indicator initialization only)
  6. Chronological ordering
  7. Return clean dataset ready for training

CRITICAL RULE: Label thresholds MUST be computed from TRAINING DATA ONLY.
    Use compute_train_thresholds() to fit thresholds, then pass them
    to build_dataset(thresholds=...) for all splits (train/val/test).
"""

import pandas as pd
import numpy as np
from database.db import read_sql
from datasets.labeling import generate_labels, compute_thresholds, _to_ist_date
from utils.logger import get_logger

logger = get_logger("dataset_builder")

# Columns to exclude from training features
META_COLS = ['timestamp', 'symbol', 'feature_version', 'created_at']

# Target numeric features for the ML model
# Feature Set v1.0: Removed sma20/sma50 (r=0.9996 vs ema20/ema50).
# Added return_*, body_pct, rolling_volatility, log_volume, gap_pct,
# opening_range_breakout_pct, day_range_pct, dist_from_day_*_pct,
# minutes_since_open, session_progress.
NUMERIC_FEATURES = [
    'open', 'high', 'low', 'close', 'volume',
    'ema20', 'ema50',
    'rsi', 'atr', 'adx', 'di_plus', 'di_minus',
    'macd', 'macd_signal', 'macd_hist',
    'return_1m', 'return_3m', 'return_5m',
    'high_low_pct', 'close_open_pct', 'body_pct',
    'rolling_volatility',
    'vwap', 'vwap_dist_pct',
    'volume_sma20', 'relative_volume', 'obv', 'obv_normalized',
    'log_volume',
    'gap_pct',
    'opening_range_breakout_pct',
    'day_range_pct',
    'dist_from_day_high_pct',
    'dist_from_day_low_pct',
    'minutes_since_open',
    'session_progress',
]

# Categorical features to one-hot encode
CATEGORICAL_FEATURES = ['regime', 'session']

# Columns that won't be used as features
LABEL_COLS = ['label', 'forward_return_pct']
DATE_COLS = ['date_ist']


def _filter_usable_features(df, candidate_cols):
    usable = []
    for col in candidate_cols:
        if col not in df.columns:
            continue
        if df[col].isna().all():
            logger.warning(f"Excluding feature '{col}': 100% NaN (pipeline failure)")
            continue
        usable.append(col)
    return usable


def compute_train_thresholds(df, label_horizon=10, train_end_date=None):
    df = df.copy()
    ts = pd.to_datetime(df['timestamp'])
    ist_dates = _to_ist_date(ts)
    df['_ist_date'] = ist_dates
    unique_dates = sorted(df['_ist_date'].unique())

    if train_end_date is None:
        # Must match chronological_split formula exactly.
        # chronological_split uses: idx = int(n_dates * train_pct) - 1
        # with train_pct=0.70.
        n_dates = len(unique_dates)
        idx = max(0, int(n_dates * 0.70) - 1)
        train_end_date = str(unique_dates[idx])

    train_mask = df['_ist_date'] <= pd.Timestamp(train_end_date).date()
    train_df = df[train_mask].copy()

    thresholds = compute_thresholds(train_df, horizon_minutes=label_horizon)
    thresholds['fitted_on'] = 'TRAIN_ONLY'
    thresholds['train_start_date'] = str(unique_dates[0])
    thresholds['train_end_date'] = str(train_end_date)
    thresholds['method'] = 'P33/P67'
    thresholds['horizon'] = label_horizon

    logger.info(
        f"Threshold provenance: horizon={label_horizon}m, "
        f"train={thresholds['train_start_date']} -> {thresholds['train_end_date']}, "
        f"n={thresholds['n_samples']}, "
        f"DOWN<{thresholds['down']:.4f}% UP>{thresholds['up']:.4f}%, "
        f"fitted_on={thresholds['fitted_on']}"
    )
    return thresholds


def build_dataset(df=None, label_horizon=10, drop_warmup=True, feature_cols=None, thresholds=None):
    if df is None:
        logger.info("Loading market_features from DB...")
        df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
    else:
        df = df.copy()

    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    if feature_cols is None:
        feature_cols = NUMERIC_FEATURES

    available_features = [c for c in feature_cols if c in df.columns]
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        logger.warning(f"Missing feature columns (not in source): {missing}")

    available_features = _filter_usable_features(df, available_features)
    logger.info(f"Usable features after NaN filter: {len(available_features)}/{len(feature_cols)}")

    logger.info(f"Generating {label_horizon}m labels...")
    if thresholds is not None:
        logger.info(
            f"Using precomputed train-only thresholds: "
            f"UP>{thresholds['up']:.4f}% DOWN<{thresholds['down']:.4f}% "
            f"(fitted_on={thresholds.get('fitted_on', 'unknown')})"
        )
    df = generate_labels(df, horizon_minutes=label_horizon, thresholds=thresholds)
    logger.info(f"After labeling: {len(df)} rows")

    for cat_col in CATEGORICAL_FEATURES:
        if cat_col in df.columns:
            dummies = pd.get_dummies(df[cat_col], prefix=cat_col).astype(int)
            df = pd.concat([df, dummies], axis=1)
            available_features.extend(dummies.columns.tolist())
            logger.info(f"One-hot encoded {cat_col}: {list(dummies.columns)}")

    keep_cols = ['timestamp', 'label', 'forward_return_pct']
    keep_cols.extend(available_features)
    keep_cols = [c for c in keep_cols if c in df.columns]

    dataset = df[keep_cols].copy()

    if drop_warmup:
        before = len(dataset)
        feature_cols_only = [c for c in available_features if c in dataset.columns]
        dataset = dataset.dropna(subset=feature_cols_only)
        dropped = before - len(dataset)
        if dropped > 0:
            logger.info(f"Dropped {dropped} rows with NaN features ({dropped/before*100:.1f}%)")
        else:
            logger.info("No warmup rows to drop (0 NaN in features)")

    dataset = dataset.sort_values('timestamp').reset_index(drop=True)

    logger.info(
        f"Dataset ready: {len(dataset)} rows, {len(dataset.columns)} cols "
        f"({len(available_features)} features + label + timestamp)"
    )
    return dataset


def build_datasets_for_horizons(df=None, horizons=None, drop_warmup=True):
    if horizons is None:
        horizons = [5, 10, 15]
    if df is None:
        df = read_sql("SELECT * FROM market_features ORDER BY timestamp")

    datasets = {}
    for h in horizons:
        logger.info(f"Building dataset for {h}-minute horizon")
        thresholds = compute_train_thresholds(df, label_horizon=h)
        datasets[h] = build_dataset(df, label_horizon=h, drop_warmup=drop_warmup, thresholds=thresholds)
    return datasets


def dataset_report(dataset):
    if dataset is None or len(dataset) == 0:
        return {
            "rows": 0, "columns": 0, "feature_columns": 0, "features": [],
            "missing_values": 0, "duplicates": 0, "class_balance": {},
            "start_timestamp": None, "end_timestamp": None, "error": "Empty dataset",
        }

    feature_cols = [c for c in dataset.columns if c not in META_COLS + LABEL_COLS + DATE_COLS]
    start_ts = None
    end_ts = None
    if 'timestamp' in dataset.columns:
        ts = pd.to_datetime(dataset['timestamp'])
        start_ts = str(ts.min())
        end_ts = str(ts.max())

    report = {
        "rows": len(dataset), "columns": len(dataset.columns),
        "feature_columns": len(feature_cols), "features": feature_cols,
        "missing_values": int(dataset.isna().sum().sum()),
        "duplicates": int(dataset.duplicated(subset=['timestamp']).sum()) if 'timestamp' in dataset.columns else 0,
        "start_timestamp": start_ts, "end_timestamp": end_ts,
    }

    if 'label' in dataset.columns:
        counts = dataset['label'].value_counts()
        total = len(dataset)
        report["class_balance"] = {
            "UP": int(counts.get('UP', 0)),
            "DOWN": int(counts.get('DOWN', 0)),
            "NEUTRAL": int(counts.get('NEUTRAL', 0)),
        }
        report["class_balance_pct"] = {
            "UP": round(counts.get('UP', 0) / total * 100, 2) if total > 0 else 0,
            "DOWN": round(counts.get('DOWN', 0) / total * 100, 2) if total > 0 else 0,
            "NEUTRAL": round(counts.get('NEUTRAL', 0) / total * 100, 2) if total > 0 else 0,
        }
    return report


def chronological_split(dataset, train_pct=0.70, val_pct=0.15):
    """
    Chronological 70/15/15 split using IST DATE BOUNDARIES (not row %).
    Guarantees zero date overlap between splits by assigning whole IST
    trading days to each partition.
    """
    if dataset is None or len(dataset) == 0:
        return {"method": "ist_date_boundary", "total_rows": 0,
                "train": {"rows": 0}, "validation": {"rows": 0},
                "test": {"rows": 0}, "splits": {}, "error": "Empty dataset"}

    dataset = dataset.sort_values('timestamp').reset_index(drop=True)
    ts = pd.to_datetime(dataset['timestamp'])
    ist_dates = _to_ist_date(ts)
    dataset['_ist_date'] = [str(d) for d in ist_dates]
    n = len(dataset)
    unique_dates = sorted(dataset['_ist_date'].unique())
    n_dates = len(unique_dates)

    train_date_end = int(n_dates * train_pct)
    val_date_end = int(n_dates * (train_pct + val_pct))

    train_cutoff = unique_dates[train_date_end - 1]
    val_cutoff = unique_dates[val_date_end - 1]

    train_mask = dataset['_ist_date'] <= train_cutoff
    val_mask = (dataset['_ist_date'] > train_cutoff) & (dataset['_ist_date'] <= val_cutoff)
    test_mask = dataset['_ist_date'] > val_cutoff

    splits = {
        "train": dataset[train_mask].copy(),
        "validation": dataset[val_mask].copy(),
        "test": dataset[test_mask].copy(),
    }

    for s in splits.values():
        s.drop(columns=['_ist_date'], inplace=True, errors='ignore')
    dataset.drop(columns=['_ist_date'], inplace=True, errors='ignore')

    def get_ist_dates(d):
        if len(d) == 0 or 'timestamp' not in d.columns:
            return []
        ts = pd.to_datetime(d['timestamp'])
        return sorted(set(str(d) for d in _to_ist_date(ts)))

    def get_date_range(d):
        ids = get_ist_dates(d)
        return f"{ids[0]} -> {ids[-1]}" if ids else None

    total = len(splits["train"]) + len(splits["validation"]) + len(splits["test"])
    check_pass = total == n

    train_dates_set = set(get_ist_dates(splits["train"]))
    val_dates_set = set(get_ist_dates(splits["validation"]))
    test_dates_set = set(get_ist_dates(splits["test"]))

    overlap_dates = (
        (train_dates_set & val_dates_set)
        | (train_dates_set & test_dates_set)
        | (val_dates_set & test_dates_set)
    )

    chronological_pass = False
    if train_dates_set and val_dates_set and test_dates_set:
        if (
            len(overlap_dates) == 0
            and max(train_dates_set) < min(val_dates_set)
            and max(val_dates_set) < min(test_dates_set)
        ):
            chronological_pass = True

    result = {
        "method": f"ist_date_boundary ({n_dates} dates, train={int(train_pct*100)}%/val={int(val_pct*100)}%/test={int(100-train_pct*100-val_pct*100)}%)",
        "total_rows": n,
        "train": {"rows": len(splits["train"]), "date_range": get_date_range(splits["train"]),
                  "ist_dates": get_ist_dates(splits["train"])},
        "validation": {"rows": len(splits["validation"]), "date_range": get_date_range(splits["validation"]),
                       "ist_dates": get_ist_dates(splits["validation"])},
        "test": {"rows": len(splits["test"]), "date_range": get_date_range(splits["test"]),
                 "ist_dates": get_ist_dates(splits["test"])},
        "splits": splits,
        "check": {
            "final_dataset": n, "train_rows": len(splits["train"]),
            "val_rows": len(splits["validation"]), "test_rows": len(splits["test"]),
            "sum": total, "pass": check_pass,
            "date_overlap": len(overlap_dates),
            "overlapping_dates": sorted(overlap_dates),
            "chronological_pass": chronological_pass,
        },
    }

    logger.info(
        f"Split: train={result['train']['rows']}, val={result['validation']['rows']}, "
        f"test={result['test']['rows']} | "
        f"CHECK: {total} == {n} -> {'PASS' if check_pass else 'FAIL'} | "
        f"DATE OVERLAP: {len(overlap_dates)} | "
        f"CHRONOLOGICAL: {'PASS' if chronological_pass else 'FAIL'}"
    )
    return result
