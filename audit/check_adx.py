"""
Check ADX and other NaN features in market_features table.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from database.db import read_sql

df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
print(f"Total rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")
print(f"Columns: {sorted(df.columns.tolist())}")

# Check all columns for NaN proportion
print(f"\n{'Column':25s} {'NaN%':>6s} {'NaN':>6s} {'Dtype':>10s}")
print("-" * 50)
for col in df.columns:
    nan_count = int(df[col].isna().sum())
    nan_pct = nan_count / len(df) * 100
    dtype = str(df[col].dtype)
    print(f"{col:25s} {nan_pct:5.1f}% {nan_count:6d} {dtype:>10s}")

# Check ADX specifically
print(f"\nADX non-NaN: {df['adx'].notna().sum()} / {len(df)}")
print(f"ADX unique values: {df['adx'].nunique()}")
if df['adx'].notna().sum() > 0:
    print(f"ADX non-null range: {df['adx'].min()} - {df['adx'].max()}")
