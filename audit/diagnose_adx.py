"""
Diagnose ADX in the rebuilt market_features table.
Checks actual ADX values, distribution, and identifies any issues.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from database.db import read_sql

df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
print(f"Total rows: {len(df)}")
print(f"Total cols: {len(df.columns)}")
print()

# ADX deep check
adx = df['adx']
print(f"ADX non-null count: {adx.notna().sum()} / {len(adx)}")
print(f"ADX null count: {adx.isna().sum()}")
print(f"ADX dtype: {adx.dtype}")
print()

# Sample ADX values from different parts of the dataset
print("ADX first 10 non-NaN values (tail after warmup):")
valid_adx = adx.dropna()
print(valid_adx.head(10).to_string())
print()

print(f"ADX unique count: {valid_adx.nunique()}")
print(f"ADX min: {valid_adx.min()}")
print(f"ADX max: {valid_adx.max()}")
print(f"ADX mean: {valid_adx.mean()}")
print(f"ADX std: {valid_adx.std()}")

# Check for infinity
vals = valid_adx.values
print(f"\nAny infinity values: {np.isinf(vals).sum()}")
print(f"Any -infinity values: {np.isneginf(vals).sum()}")
print(f"Any NaN still in non-null set: {pd.isna(vals).sum()}")

# Distribution summary
print(f"\nADX percentiles:")
for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    print(f"  P{p:2d}: {np.percentile(vals, p):.2f}")

# Check if all values are same constant
if valid_adx.nunique() <= 1:
    print("\nWARNING: ADX appears constant — all values are the same!")
else:
    print(f"\nOK: ADX has {valid_adx.nunique()} unique values — good variance")

# Specifically check the warmup region
print(f"\nFirst 30 rows of ADX (warmup period):")
for i in range(min(30, len(df))):
    v = adx.iloc[i]
    t = str(pd.to_datetime(df['timestamp'].iloc[i]))[11:19]
    v_str = f"{v:.2f}" if not pd.isna(v) else "NaN"
    print(f"  [{i:3d}] {t} -> adx={v_str}")
