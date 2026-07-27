"""
PHASE A+B — Diagnose and fix dataset_builder 100% drop
========================================================
Root cause so far: adx column is 100% NaN (10875/10875 rows).
This script reproduces the exact merge/backfill logic, then proposes fixes.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from database.db import read_sql
from datasets.labeling import generate_labels

# Exact feature list
NUMERIC_FEATURES = [
    'open', 'high', 'low', 'close', 'volume',
    'ema20', 'ema50', 'sma20', 'sma50',
    'rsi', 'atr', 'adx', 'di_plus', 'di_minus',
    'macd', 'macd_signal', 'macd_hist',
    'vwap', 'vwap_dist_pct',
    'volume_sma20', 'relative_volume', 'obv', 'obv_normalized',
]
CAT_FEATURES = ['regime', 'session']

df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
print(f"1. Raw data: {len(df)} rows x {len(df.columns)} cols")

# Check which features are fully NaN
available = [c for c in NUMERIC_FEATURES if c in df.columns]
fully_nan = [c for c in available if df[c].isna().all()]
partially_nan = [c for c in available if not df[c].isna().all() and df[c].isna().any()]
clean = [c for c in available if not df[c].isna().any()]

print(f"\n2. Feature NaN analysis:")
print(f"   Fully NaN (will be excluded): {fully_nan}")
print(f"   Partially NaN (warmup rows): {partially_nan}")
print(f"   Clean (0 NaN): {clean}")

# Strategy: exclude fully-NaN features from feature list
good_features = [c for c in available if not df[c].isna().all()]
print(f"\n3. Good features for training: {good_features} ({len(good_features)}/{len(available)})")

# Run labeling
lbl = generate_labels(df, horizon_minutes=10)
print(f"\n4. After labeling: {len(lbl)} rows")

# One-hot encode
regime_dummies = pd.get_dummies(lbl['regime'], prefix='regime')
session_dummies = pd.get_dummies(lbl['session'], prefix='session')

# Need to convert bool -> int for pandas to handle NaN properly
for d in [regime_dummies, session_dummies]:
    for c in d.columns:
        d[c] = d[c].astype(int)

lbl2 = pd.concat([lbl, regime_dummies, session_dummies], axis=1)

# Build feature list with dummies
final_features = (
    good_features +
    list(regime_dummies.columns) +
    list(session_dummies.columns)
)
final_features = [c for c in final_features if c in lbl2.columns]

# Build dataset
keep = ['timestamp', 'label', 'forward_return_pct'] + final_features
keep = [c for c in keep if c in lbl2.columns]

ds = lbl2[keep].copy()

# Drop ONLY where INPUT features are NaN
feature_only = [c for c in final_features if c in ds.columns]
before = len(ds)
any_nan_mask = ds[feature_only].isna().any(axis=1)
ds_clean = ds[~any_nan_mask].copy()

print(f"\n5. Dataset after NaN drop:")
print(f"   Before: {before} rows, {len(ds.columns)} cols")
print(f"   Dropped: {any_nan_mask.sum()} rows ({any_nan_mask.sum()/before*100:.1f}%)")
print(f"   After: {len(ds_clean)} rows")

# Check for duplicate timestamps
if 'timestamp' in ds_clean.columns:
    dups = ds_clean['timestamp'].duplicated().sum()
    print(f"   Duplicate timestamps: {dups}")

# Check class balance
if 'label' in ds_clean.columns:
    counts = ds_clean['label'].value_counts()
    total = len(ds_clean)
    print(f"\n6. Class balance:")
    for label in ['UP', 'DOWN', 'NEUTRAL']:
        c = counts.get(label, 0)
        print(f"   {label:8s}: {c:5d} ({c/total*100:.1f}%)")

print(f"\n7. Final shape: {ds_clean.shape}")
print(f"\n8. Verdict: READY" if len(ds_clean) > 0 else "\n8. Verdict: STILL BROKEN")
