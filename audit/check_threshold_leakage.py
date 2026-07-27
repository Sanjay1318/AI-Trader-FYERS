"""
Check Threshold Leakage — Milestone 2
=======================================
Verifies that thresholds are computed from TRAINING DATA ONLY and
that validation/test sets use the frozen train-derived thresholds.

Ensures no data leakage through threshold selection.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from database.db import read_sql
from datasets.labeling import compute_thresholds, generate_labels, _to_ist_date, label_distribution

HORIZONS = [5, 10, 15]


def _date_split_by_day(df):
    """Split by complete IST trading dates: 70% train, 15% val, 15% test."""
    ts = pd.to_datetime(df['timestamp'])
    ist_dates = _to_ist_date(ts)
    unique_dates = sorted(set(ist_dates))
    n = len(unique_dates)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    train_dates = set(unique_dates[:train_end])
    val_dates = set(unique_dates[train_end:val_end])
    test_dates = set(unique_dates[val_end:])

    train_mask = ist_dates.isin(train_dates)
    val_mask = ist_dates.isin(val_dates)
    test_mask = ist_dates.isin(test_dates)

    return {
        "train": df[train_mask].sort_values('timestamp').reset_index(drop=True),
        "validation": df[val_mask].sort_values('timestamp').reset_index(drop=True),
        "test": df[test_mask].sort_values('timestamp').reset_index(drop=True),
        "train_dates": sorted(train_dates),
        "val_dates": sorted(val_dates),
        "test_dates": sorted(test_dates),
    }


def check_horizon(horizon_minutes, df, split):
    """Check threshold provenance for one horizon."""
    print(f"\n{'='*60}")
    print(f"  HORIZON: {horizon_minutes}m")
    print(f"{'='*60}")

    train_df = split["train"]
    val_df = split["validation"]
    test_df = split["test"]

    print(f"\n  TRAIN dates:  {split['train_dates'][0]} -> {split['train_dates'][-1]}  ({len(train_df)} rows)")
    print(f"  VAL dates:    {split['val_dates'][0]} -> {split['val_dates'][-1]}  ({len(val_df)} rows)")
    print(f"  TEST dates:   {split['test_dates'][0]} -> {split['test_dates'][-1]}  ({len(test_df)} rows)")

    # Compute thresholds on TRAIN data only
    train_thresholds = compute_thresholds(train_df, horizon_minutes=horizon_minutes)
    n_train_samples = train_thresholds.get("n_samples", 0)
    print(f"\n  TRAIN return count:  {n_train_samples}")
    print(f"  TRAIN P33 (DOWN):    {train_thresholds['down']:+.4f}%")
    print(f"  TRAIN P67 (UP):      {train_thresholds['up']:+.4f}%")
    print(f"  Frozen DOWN threshold: {train_thresholds['down']:+.4f}%")
    print(f"  Frozen UP threshold:   {train_thresholds['up']:+.4f}%")

    # Apply frozen thresholds to ALL three splits
    print(f"\n  Applying FROZEN thresholds to each split:")
    for name, split_df in [("TRAIN", train_df), ("VALIDATION", val_df), ("TEST", test_df)]:
        labeled = generate_labels(split_df, horizon_minutes=horizon_minutes,
                                  thresholds=train_thresholds)
        dist = label_distribution(labeled)
        print(f"\n    {name}:")
        print(f"      Rows: {dist['total']}")
        print(f"      UP:     {dist['up']:>5d} ({dist['up_pct']:.1f}%)")
        print(f"      DOWN:   {dist['down']:>5d} ({dist['down_pct']:.1f}%)")
        print(f"      NEUTRAL:{dist['neutral']:>5d} ({dist['neutral_pct']:.1f}%)")

        if name == "TRAIN":
            train_dist = dist
            train_labeled = labeled

    # Verify: train should be approx 33/33/34, val/test should be realistic
    up_range = abs(train_dist["up_pct"] - 33.3)
    down_range = abs(train_dist["down_pct"] - 33.3)

    if up_range < 5 and down_range < 5:
        print(f"\n  OK: Train distribution is approximately balanced")
    else:
        print(f"\n  INFO: Train distribution deviates from perfect 33/33/34")
        print(f"  (UP={train_dist['up_pct']:.1f}% is {up_range:.1f}pp from 33.3)")
        print(f"  (DOWN={train_dist['down_pct']:.1f}% is {down_range:.1f}pp from 33.3)")

    return train_thresholds


def main():
    print("="*70)
    print("  CHECK THRESHOLD LEAKAGE — Milestone 2")
    print("  Verifies thresholds are fit on TRAIN only and frozen for VAL/TEST")
    print("="*70)

    df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
    print(f"\n  Loaded {len(df)} rows from market_features")

    split = _date_split_by_day(df)

    thresholds_map = {}
    for h in HORIZONS:
        thresholds_map[h] = check_horizon(h, df, split)

    print(f"\n{'='*70}")
    print(f"  THRESHOLD PROVENANCE:")
    print(f"  THRESHOLDS FITTED ON: TRAIN ONLY")
    print(f"  VALIDATION USES: FROZEN TRAIN THRESHOLDS")
    print(f"  TEST USES:       FROZEN TRAIN THRESHOLDS")
    for h in HORIZONS:
        t = thresholds_map[h]
        print(f"  {h:2d}m: UP>{t['up']:+.4f}%  DOWN<{t['down']:+.4f}%  (n={t['n_samples']})")
    print(f"{'='*70}")
    return thresholds_map


if __name__ == "__main__":
    main()
