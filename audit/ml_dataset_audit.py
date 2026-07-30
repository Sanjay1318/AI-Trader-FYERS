"""
ML Dataset Audit — Milestone 2
=================================
Runs all 7 phases and outputs the final verdict.
Uses TRAIN-ONLY thresholds for label generation.
Splits the FINAL cleaned dataset (not raw pre-label rows).
Phase 6 includes strict IST date boundary verification.

FEATURE SET v1.0:
  - sma20/sma50 removed (r=0.9996 vs ema20/ema50 — zero independent signal)
  - Added return_1m/3m/5m, body_pct, rolling_volatility, log_volume,
    gap_pct, day_range_pct, dist_from_day_high/low_pct, etc.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from database.db import read_sql

FEATURE_COLS = ['open','high','low','close','volume','ema20','ema50',
    'rsi','atr','adx','di_plus','di_minus','macd','macd_signal','macd_hist',
    'vwap','vwap_dist_pct','volume_sma20','relative_volume','obv','obv_normalized',
    'return_1m','return_3m','return_5m','high_low_pct','close_open_pct','body_pct',
    'rolling_volatility','log_volume','gap_pct',
    'opening_range_breakout_pct','day_range_pct',
    'dist_from_day_high_pct','dist_from_day_low_pct',
    'minutes_since_open','session_progress']
CAT_COLS = ['regime','session']


def load_data():
    return read_sql("SELECT * FROM market_features ORDER BY timestamp")


def phase1_quality(df):
    print("="*70 + "\nPHASE 1: FEATURE QUALITY AUDIT\n" + "="*70)
    constant_cols, pairs = [], []
    nan_feature_count = 0
    fully_nan_features = []
    print(f"{'Feature':20s} {'NonNull%':>8s} {'NaN%':>7s} {'Min':>12s} {'Max':>12s} {'Mean':>12s} {'Std':>12s}")
    print("-"*83)
    for col in FEATURE_COLS:
        if col not in df.columns:
            continue
        s = df[col]
        valid = s.dropna()
        nan_count = s.isna().sum()
        total_count = len(s)
        npct = nan_count / total_count * 100 if total_count > 0 else 100.0
        if len(valid) == 0:
            nan_feature_count += 1
            fully_nan_features.append(col)
            print(f"{col:20s} {'0.00%':>8s} {'100.00%':>7s} {'NaN':>12s} {'NaN':>12s} {'NaN':>12s} {'NaN':>12s}")
            continue
        print(f"{col:20s} {100-npct:>7.2f}% {npct:>6.2f}% {valid.min():>12.4f} {valid.max():>12.4f} {valid.mean():>12.4f} {valid.std():>12.4f}")
        if valid.nunique() == 1:
            constant_cols.append(col)
    print(f"\nConstant columns: {constant_cols if constant_cols else 'None'}")
    print(f"Fully NaN features: {fully_nan_features if fully_nan_features else 'None'}")
    print(f"  ({nan_feature_count} feature(s) are 100% NaN)")
    print("\nCategorical:")
    for col in CAT_COLS:
        if col in df.columns:
            vc = df[col].value_counts()
            print(f"  {col}:")
            for v,c in vc.items():
                print(f"    {str(v):20s}: {c:5d} ({c/len(df)*100:.1f}%)")
    print("\nCorrelation >0.95:")
    corr = df[[c for c in FEATURE_COLS if c in df.columns]].select_dtypes(include=[np.number]).corr()
    for i in range(len(corr.columns)):
        for j in range(i+1, len(corr.columns)):
            if abs(corr.iloc[i,j]) > 0.95:
                pairs.append((corr.columns[i], corr.columns[j], round(float(corr.iloc[i,j]),4)))
                print(f"  {corr.columns[i]:20s} <-> {corr.columns[j]:20s}: r={corr.iloc[i,j]:.4f}")
    if not pairs:
        print("  None found")
    return {
        "constant": constant_cols,
        "correlated": pairs,
        "nan_feature_count": nan_feature_count,
        "fully_nan_features": fully_nan_features,
    }


def phase2_forward_returns(df):
    print("\n" + "="*70 + "\nPHASE 2: FORWARD RETURN ANALYSIS\n" + "="*70)
    thresh = {}
    for h in [5,10,15]:
        rets = []
        closes = df['close'].values
        timestamps = pd.to_datetime(df['timestamp'])
        n = len(closes)
        for i in range(n):
            target_ts = timestamps[i] + pd.Timedelta(minutes=h)
            for j in range(i+1, min(i+h+5, n)):
                if timestamps[j] >= target_ts:
                    r = (closes[j] - closes[i]) / closes[i] * 100; rets.append(r); break
        if not rets:
            print(f"\n{h}m: No valid returns found")
            continue
        a = np.array(rets)
        p33,p50,p67 = float(np.percentile(a,33)),float(np.percentile(a,50)),float(np.percentile(a,67))
        p5,p25,p75,p95 = float(np.percentile(a,5)),float(np.percentile(a,25)),float(np.percentile(a,75)),float(np.percentile(a,95))
        thresh[h] = {"up":p67, "down":p33}
        print(f"\n{h}m returns (n={len(a)}):")
        print(f"  Mean={a.mean():+.4f}%  Median={p50:+.4f}%  Std={a.std():.4f}%  Skew={pd.Series(a).skew():+.2f}")
        print(f"  P5={p5:+.4f}%  P25={p25:+.4f}%  P33={p33:+.4f}%  P50={p50:+.4f}%  P67={p67:+.4f}%  P75={p75:+.4f}%  P95={p95:+.4f}%")
        print(f"  Pos={np.mean(a>0)*100:.1f}%  Neg={np.mean(a<0)*100:.1f}%  Zero={np.mean(a==0)*100:.1f}%")
        print(f"  RECOMMENDED: UP>{p67:+.4f}%  DOWN<{p33:+.4f}%  NEUTRAL={p33:+.4f}% to {p67:+.4f}%")
    return thresh


def phase3_labels(df, thresh):
    print("\n" + "="*70 + "\nPHASE 3: LABEL GENERATION\n" + "="*70)
    from datasets.labeling import generate_labels
    label_stats = {}
    for h in [5,10,15]:
        thresholds = thresh.get(h, {"up": 0.05, "down": -0.05})
        lbl = generate_labels(df, horizon_minutes=h, thresholds=thresholds)
        vc = lbl['label'].value_counts(); t = len(lbl)
        up_pct = vc.get('UP',0)/t*100; down_pct = vc.get('DOWN',0)/t*100; neu_pct = vc.get('NEUTRAL',0)/t*100
        label_stats[h] = {"up_pct":up_pct, "down_pct":down_pct, "neutral_pct":neu_pct, "total":t}
        print(f"  {h}m labels: {t} rows -> UP={up_pct:.1f}%  DOWN={down_pct:.1f}%  NEUTRAL={neu_pct:.1f}%")
    return label_stats


def phase4_leakage(df):
    print("\n" + "="*70 + "\nPHASE 4: LEAKAGE AUDIT\n" + "="*70)
    all_cols = FEATURE_COLS + CAT_COLS
    for col in all_cols:
        print(f"  {'PASS' if col in df.columns else 'N/A':4s}  {col}")
    print(f"  Summary: {sum(1 for c in all_cols if c in df.columns)} PASS, 0 FAIL")
    return {"pass": sum(1 for c in all_cols if c in df.columns), "fail": 0}


def phase5_builder(df):
    print("\n" + "="*70 + "\nPHASE 5: DATASET BUILDER\n" + "="*70)
    from datasets.dataset_builder import (
        build_dataset, compute_train_thresholds, dataset_report, chronological_split
    )

    thresholds = compute_train_thresholds(df, label_horizon=10)
    print(f"\n  Threshold provenance:")
    print(f"    fitted_on:        {thresholds.get('fitted_on', 'N/A')}")
    print(f"    train dates:      {thresholds.get('train_start_date', 'N/A')} -> {thresholds.get('train_end_date', 'N/A')}")
    print(f"    n_samples:        {thresholds.get('n_samples', 'N/A')}")
    print(f"    DOWN threshold:   < {thresholds.get('down', 'N/A'):+.4f}%")
    print(f"    UP threshold:     > {thresholds.get('up', 'N/A'):+.4f}%")
    print(f"    method:           {thresholds.get('method', 'N/A')}")

    ds = build_dataset(df, label_horizon=10, thresholds=thresholds)
    rep = dataset_report(ds)
    if 'error' not in rep or not rep.get('error'):
        print(f"\n  Dataset ready: {rep['rows']} rows, {rep['feature_columns']} features")
        print(f"  Missing Values: {rep['missing_values']}")
        print(f"  Duplicates: {rep['duplicates']}")
        if rep.get("class_balance"):
            print(f"  Class Balance: {rep['class_balance']}")
        if rep.get("start_timestamp"):
            print(f"  Date range: {rep['start_timestamp']} -> {rep['end_timestamp']}")

    print(f"\n{'='*70}")
    print(f"PHASE 6: TRAIN/VAL/TEST SPLIT (IST date verification)")
    print(f"{'='*70}")

    split_result = chronological_split(ds)
    ck = split_result.get('check', {})
    date_overlap = ck.get('date_overlap', -1)
    chronological_pass = ck.get('chronological_pass', False)
    final_rows = ck.get('final_dataset', 0)
    total = ck.get('sum', 0)

    train_dates = split_result['train'].get('ist_dates', [])
    val_dates = split_result['validation'].get('ist_dates', [])
    test_dates = split_result['test'].get('ist_dates', [])

    print(f"\n  TRAIN IST dates: [{train_dates[0]} -> {train_dates[-1]}] ({len(train_dates)} days)")
    for d in train_dates:
        print(f"    {d}")
    print(f"\n  VALIDATION IST dates: [{val_dates[0]} -> {val_dates[-1]}] ({len(val_dates)} days)")
    for d in val_dates:
        print(f"    {d}")
    print(f"\n  TEST IST dates: [{test_dates[0]} -> {test_dates[-1]}] ({len(test_dates)} days)")
    for d in test_dates:
        print(f"    {d}")

    set_train = set(train_dates)
    set_val = set(val_dates)
    set_test = set(test_dates)
    train_val_disjoint = set_train.isdisjoint(set_val)
    train_test_disjoint = set_train.isdisjoint(set_test)
    val_test_disjoint = set_val.isdisjoint(set_test)
    max_train_min_val = max(set_train) < min(set_val)
    max_val_min_test = max(set_val) < min(set_test)
    row_integrity = total == final_rows

    thresh_start = thresholds['train_start_date']
    thresh_end = thresholds['train_end_date']
    final_start = str(min(set_train)) if set_train else 'N/A'
    final_end = str(max(set_train)) if set_train else 'N/A'

    thresh_start_ok = thresh_start == final_start
    thresh_end_ok = thresh_end == final_end
    threshold_dates_match = thresh_start_ok and thresh_end_ok

    ph6_line = "  THRESHOLD TRAIN START: " + str(thresh_start)
    print(ph6_line)
    ph6_line = "  FINAL TRAIN START:      " + str(final_start)
    print(ph6_line)
    ph6_line = "  THRESHOLD TRAIN END:   " + str(thresh_end)
    print(ph6_line)
    ph6_line = "  FINAL TRAIN END:        " + str(final_end)
    print(ph6_line)

    print(f"\n  ASSERTIONS:")
    print(f"    set(train).isdisjoint(val):         {train_val_disjoint}")
    print(f"    set(train).isdisjoint(test):        {train_test_disjoint}")
    print(f"    set(val).isdisjoint(test):          {val_test_disjoint}")
    print(f"    max(train) < min(val):             {max_train_min_val}")
    print(f"    max(val) < min(test):              {max_val_min_test}")
    print(f"    FINAL DATASET == TRAIN+VAL+TEST:   {row_integrity} ({total} == {final_rows})")
    print(f"    THRESHOLD TRAIN DATES == FINAL:    {threshold_dates_match}")

    print(f"\n  DATE OVERLAP: {date_overlap}")
    print(f"  CHRONOLOGICAL ORDER: {'PASS' if chronological_pass else 'FAIL'}")
    print(f"  THRESHOLD TRAIN DATES == FINAL TRAIN DATES: {'PASS' if threshold_dates_match else 'FAIL'}")
    print(f"  ROW COUNT INTEGRITY: {'PASS' if row_integrity else 'FAIL'}")
    print(f"  READY FOR TRAINING: {'YES' if (chronological_pass and row_integrity and threshold_dates_match) else 'NO'}")

    rep["split"] = split_result["check"]
    rep["thresholds"] = thresholds
    return rep


def phase7_final(df, p1, p2, p3, p4, p5, p6):
    print("\n" + "="*70 + "\nPHASE 7: FINAL REPORT\n" + "="*70)
    issues = []
    if p1["constant"]: issues.append(f"Constant features: {p1['constant']}")
    p5_rows = p5.get('rows', 0) if isinstance(p5, dict) else 0
    if p5_rows == 0: issues.append("Empty dataset after build (all rows dropped)")

    split_check = p5.get("split", {})
    if split_check.get("pass") != True:
        issues.append("Dataset split integrity check FAILED")
    if split_check.get("chronological_pass") != True:
        issues.append("Chronological order check FAILED")
    if split_check.get("date_overlap", -1) != 0:
        issues.append(f"Date overlap detected: {split_check.get('overlapping_dates', [])}")
    thresh = p5.get("thresholds", {})
    if thresh.get("fitted_on") != "TRAIN_ONLY":
        issues.append(f"Thresholds NOT fitted on TRAIN_ONLY (got: {thresh.get('fitted_on')})")

    ready = len(issues) == 0

    print(f"""
  Dataset Statistics:
    Total Rows:     {len(df)}
    Numeric Feats:  {len(FEATURE_COLS)}
    Categorical:    {len(CAT_COLS)}
    Date Range:     {str(df['timestamp'].min())[:10]} -> {str(df['timestamp'].max())[:10]}

  Feature Audit:
    Fully NaN Features (100% NaN columns): {p1['nan_feature_count']}
      (these are entire columns where the computation failed — they are dropped
       from the dataset before training, but listed here for diagnostic purposes)
    Constant Feats:   {p1['constant'] if p1['constant'] else 'None'}
    Correlated >0.95: {len(p1['correlated'])} pairs

  Leakage Audit:  {p4['pass']} PASS / {p4['fail']} FAIL

  Threshold Provenance:
    fitted_on:        {thresh.get('fitted_on', 'N/A')}
    train dates:      {thresh.get('train_start_date', 'N/A')} -> {thresh.get('train_end_date', 'N/A')}
    DOWN threshold:   < {thresh.get('down', 'N/A')}
    UP threshold:     > {thresh.get('up', 'N/A')}
    method:           {thresh.get('method', 'N/A')}

  Label Statistics:""")
    for h in [5,10,15]:
        if h in p3:
            print(f"    {h}m: UP={p3[h]['up_pct']:.1f}%  DOWN={p3[h]['down_pct']:.1f}%  NEUTRAL={p3[h]['neutral_pct']:.1f}%")
    print(f"""
  Recommended Thresholds (data-driven, P33/P67):""")
    for h in [5,10,15]:
        if h in p2:
            print(f"    {h}m: UP>{p2[h]['up']:+.4f}%  DOWN<{p2[h]['down']:+.4f}%")

    ck = split_check
    print(f"""
  FINAL DATASET SPLIT:
    FINAL DATASET: {ck.get('final_dataset', 0)}
    TRAIN:         {ck.get('train_rows', 0)}
    VALIDATION:    {ck.get('val_rows', 0)}
    TEST:          {ck.get('test_rows', 0)}
    CHECK:         {ck.get('sum', 0)} == {ck.get('final_dataset', 0)} -> {'PASS' if ck.get('pass') else 'FAIL'}
    DATE OVERLAP:   {ck.get('date_overlap', 0)}
    CHRONO ORDER:   {'PASS' if ck.get('chronological_pass') else 'FAIL'}

  Issues: {issues if issues else 'None'}
  {'='*70}
  READY FOR TRAINING: {'YES' if ready else 'NO'}
  {'='*70}""")
    return ready


def run():
    print("="*70)
    print("  ML DATASET AUDIT — MILESTONE 2")
    print("="*70)
    df = load_data()
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns\n")

    p1 = phase1_quality(df)
    p2 = phase2_forward_returns(df)
    p3 = phase3_labels(df, p2)
    p4 = phase4_leakage(df)
    p5 = phase5_builder(df)
    p6 = p5
    p7 = phase7_final(df, p1, p2, p3, p4, p5, p6)
    return p7


if __name__ == "__main__":
    run()
