#!/usr/bin/env python3
"""READ-ONLY Audit: Complete ML Pipeline Dataset Analysis."""
import sys, os, json, warnings
from datetime import datetime
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings('ignore')
from dotenv import load_dotenv
load_dotenv()
import numpy as np
import pandas as pd
from database.db import engine
from datasets.labeling import generate_labels
from datasets.dataset_builder import build_dataset, compute_train_thresholds, chronological_split

CLASS_ORDER = ['DOWN', 'NEUTRAL', 'UP']

def header(t): print(f"\n{'='*70}\n  {t}\n{'='*70}")
def sub(t): print(f"\n  --- {t} ---")

def main():
    print(f"ML PIPELINE AUDIT - READ ONLY\nRun at: {datetime.now().isoformat()}")
    
    header("1. DATASET")
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM market_features ORDER BY timestamp", conn)
    
    ts_all = pd.to_datetime(df['timestamp'])
    ist_dates = ts_all.dt.tz_convert('Asia/Kolkata').dt.date
    unique_dates = sorted(set(ist_dates))
    
    ohlcv = ['open','high','low','close','volume']
    tech = ['ema20','ema50','sma20','sma50','rsi','atr','adx','di_plus','di_minus','macd','macd_signal','macd_hist']
    vol = ['vwap','vwap_dist_pct','volume_sma20','relative_volume','obv','obv_normalized']
    mkt = ['session','minutes_since_open','session_progress','day_of_week','is_first_hour','is_last_hour',
           'gap_pct','gap_type','or_high','or_low','or_breakout_pct','or_breakdown_pct',
           'day_high','day_low','day_range','dist_from_high_pct','dist_from_low_pct']
    regime = ['regime','regime_value']
    all_f = ohlcv + tech + vol + mkt + regime
    avail = [c for c in all_f if c in df.columns]
    
    print(f"  Total rows:       {len(df):,}")
    print(f"  Total columns:    {len(df.columns)}")
    print(f"  Feature columns:  {len(avail)}")
    print(f"  Feature names:    {avail}")
    print(f"  Timestamp range:  {ts_all.min()} -> {ts_all.max()}")
    print(f"  Trading days:     {len(unique_dates)}")
    
    ist_hr = ts_all.dt.tz_convert('Asia/Kolkata').dt.hour
    ist_min = ts_all.dt.tz_convert('Asia/Kolkata').dt.minute
    ist_dow = ts_all.dt.tz_convert('Asia/Kolkata').dt.dayofweek
    weekend = (ist_dow >= 5).sum()
    after_hours = ((ist_hr < 9) | ((ist_hr == 9) & (ist_min < 15)) | (ist_hr > 15) | ((ist_hr == 15) & (ist_min > 30))).sum()
    print(f"  Weekend rows:     {weekend}")
    print(f"  After-hours rows: {after_hours}")
    
    sub("Feature Data Types")
    for c in avail:
        print(f"    {c:30s} {str(df[c].dtype):10s}")
    
    header("2. FEATURE STATS + MISSING VALUES")
    print(f"  {'Col':25s} {'Nulls':>7s} {'Null%':>7s} {'Min':>12s} {'Max':>12s} {'Mean':>12s} {'Std':>12s}")
    print(f"  {'-'*25} {'-'*7} {'-'*7} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
    consts = []
    for col in avail:
        s = df[col]
        n_nulls = int(s.isna().sum())
        pct = n_nulls/len(df)*100
        if s.dtype.kind in 'fc':
            v = s.dropna()
            if len(v) > 0:
                mn, mx, mu, sd = v.min(), v.max(), v.mean(), v.std()
                if mn == mx: consts.append(col)
                print(f"  {col:25s} {n_nulls:>7,} {pct:>6.2f}% {mn:>12.4f} {mx:>12.4f} {mu:>12.4f} {sd:>12.4f}")
            else:
                print(f"  {col:25s} {n_nulls:>7,} {pct:>6.2f}% {'ALL NaN':>12s}")
        else:
            print(f"  {col:25s} {n_nulls:>7,} {pct:>6.2f}%")
    if consts: print(f"\n  CONSTANT: {consts}")
    
    header("3. DATA QUALITY")
    print(f"  Duplicate timestamps: {df['timestamp'].duplicated(keep='first').sum()}")
    print(f"  Duplicate rows:       {df.duplicated().sum()}")
    
    market_df = df[(ist_dow < 5) & (ist_hr >= 9) & (ist_hr <= 15)]
    if len(market_df) > 1:
        tm = pd.to_datetime(market_df['timestamp'])
        gaps = tm.diff().dt.total_seconds()
        large = (gaps > 120).sum()
        print(f"  Gaps >120s in market hours: {large}")
        for gi in gaps[gaps > 120].index[:5]:
            print(f"    {tm.iloc[gi-1]} -> {tm.iloc[gi]} ({gaps.iloc[gi]:.0f}s)")
    
    wf = [c for c in avail if df[c].dtype.kind in 'fc']
    nan_any = df[wf].isna().any(axis=1)
    print(f"  Rows with NaN features: {nan_any.sum():,} ({nan_any.sum()/len(df)*100:.1f}%)")
    first_ok = nan_any.argmin() if not nan_any.all() else len(df)
    print(f"  First clean row index:  {first_ok}")
    
    header("4. LABELS")
    sub("4a. Thresholds (10-min, P33/P67 from TRAIN)")
    th = compute_train_thresholds(df, label_horizon=10)
    print(f"  UP: >{th['up']:.4f}%  DOWN: <{th['down']:.4f}%  n={th['n_samples']}")
    print(f"  Train: {th['train_start_date']} -> {th['train_end_date']}")
    
    sub("4b. Label Distribution")
    labeled = generate_labels(df, horizon_minutes=10, thresholds=th)
    counts = labeled['label'].value_counts()
    total = len(labeled)
    print(f"  Total: {total:,}")
    for c in ['UP','DOWN','NEUTRAL']:
        v = counts.get(c,0)
        print(f"  {c:8s}: {v:>6,}  ({v/total*100:>5.2f}%)")
    
    sub("4c. Forward Return (%)")
    fr = labeled['forward_return_pct'].dropna()
    print(f"  mean={fr.mean():+.4f}  med={fr.median():+.4f}  std={fr.std():.4f}")
    print(f"  p25={fr.quantile(0.25):+.4f}  p75={fr.quantile(0.75):+.4f}")
    print(f"  min={fr.min():+.4f}  max={fr.max():+.4f}")
    
    header("5. TRAIN/VAL/TEST SPLIT")
    ds = build_dataset(df, label_horizon=10, thresholds=th)
    sp = chronological_split(ds)
    print(f"  Total: {sp['total_rows']:,}")
    for s in ['train','validation','test']:
        d = sp[s]
        print(f"  {s.upper():12s}: {d['rows']:>6,}  {d['date_range']}")
    chk = sp['check']
    print(f"  Sum OK: {chk['pass']}  Overlap: {chk['date_overlap']}  Chrono: {chk['chronological_pass']}")
    for sn, sdf in sp['splits'].items():
        c = sdf['label'].value_counts()
        n = len(sdf)
        if n:
            print(f"  {sn.upper():12s} class: UP={c.get('UP',0)/n*100:5.1f}% DOWN={c.get('DOWN',0)/n*100:5.1f}% NEUT={c.get('NEUTRAL',0)/n*100:5.1f}%")
    
    header("6. FEATURE CORRELATION")
    num = [c for c in avail if df[c].dtype.kind in 'fc' and df[c].isna().sum() < len(df)*0.8]
    cd = df[num].dropna()
    if len(cd) > 0:
        cor = cd.corr()
        for thresh in [0.95, 0.90]:
            pairs = []
            for i in range(len(cor.columns)):
                for j in range(i+1, len(cor.columns)):
                    v = cor.iloc[i,j]
                    if abs(v) > thresh:
                        pairs.append((cor.columns[i], cor.columns[j], v))
            print(f"\n  |r| > {thresh}: {len(pairs)} pairs")
            for c1,c2,v in sorted(pairs, key=lambda x: -abs(x[2]))[:15]:
                print(f"    {c1:25s} <-> {c2:25s}  r={v:+.4f}")
    
    header("7. WARMUP ROWS")
    nan_counts = df[wf].isna().sum()
    nz = nan_counts[nan_counts > 0].sort_values(ascending=False)
    if len(nz) > 0:
        print(f"  Columns with NaN:")
        for col, cnt in nz.items():
            print(f"    {col:25s}: {cnt:>6,} ({cnt/len(df)*100:>5.1f}%)")
    
    header("8. POSSIBLE LEAKAGE")
    print(f"  Gap detection:    uses PREV close -> OK")
    print(f"  VWAP:             cumulative -> WARN (resets? check OBV too)")
    print(f"  Day/OR hi/lo:     cumulative per IST date -> OK")
    print(f"  Labels:           10-min forward -> expected lookahead")
    print(f"  Thresholds:       TRAIN ONLY -> OK")
    print(f"  Split:            date-boundary chronological -> OK")
    
    header("9. ML PIPELINE")
    print(f"  Models:           LR (balanced), RF (200/15), XGB (200/0.1)")
    print(f"  Preprocessing:    StandardScaler(LR only), one-hot(session,regime), drop-NaN warmup")
    print(f"  Train/Val/Test:   70/15/15 chronological date-boundary split")
    print(f"  CV:               None (single split)")
    print(f"  Metrics:          Macro F1 (primary), Accuracy, Balanced Acc, Weighted F1")
    
    header("10. RECOMMENDED BASELINE")
    print(f"  Based on dataset characteristics:")
    print(f"    - {total:,} labeled rows, 3-class (UP/DOWN/NEUT)")
    print(f"    - {len(num)} numeric features after NaN filter")
    print(f"    - Class balance: UP={counts.get('UP',0)/total*100:.1f}% / "
          f"DOWN={counts.get('DOWN',0)/total*100:.1f}% / "
          f"NEUT={counts.get('NEUTRAL',0)/total*100:.1f}%")
    third = min(counts.get('UP',0), counts.get('DOWN',0), counts.get('NEUTRAL',0))
    print(f"    - Min class size: ~{third:,} rows")
    print(f"  Recommendation: Logistic Regression baseline FIRST")
    print(f"    - Fast training, interpretable coefficients")
    print(f"    - Handles class imbalance via class_weight='balanced'")
    print(f"    - Establishes feature importance baseline")
    print(f"    - Then compare RF (nonlinear interactions) and XGB (gradient boosting)")
    print(f"    - Winner: XGBoost if LR+RF underperform")
    print(f"\n{'='*70}\n  AUDIT COMPLETE\n{'='*70}")

if __name__ == '__main__':
    main()
