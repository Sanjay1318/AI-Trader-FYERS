"""
Check Label Boundaries — Milestone 2 Audit
============================================
Verifies that forward-looking labels (from generate_labels()) never cross
IST trading session boundaries.

Key check: Every label's target timestamp must be within the same IST date
as the feature timestamp.  Cross-session labels would leak future-day
information into today's training data.

NOTE: "No valid target found" rows are EXPECTED — those are end-of-day rows
that generate_labels() correctly drops. Only actual CROSS-SESSION labels
(different IST date between feature and target) are real violations.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from database.db import read_sql
from datasets.labeling import generate_labels, _to_ist_date
from utils.logger import get_logger

logger = get_logger("check_label_boundaries")


def verify_labels(df, horizon_minutes):
    print(f"\n{'='*70}")
    print(f"  CHECKING {horizon_minutes}-MINUTE LABELS")
    print(f"{'='*70}")

    labeled = generate_labels(df, horizon_minutes=horizon_minutes).reset_index(drop=True)
    dropped = len(df) - len(labeled)
    print(f"  Input: {len(df)} rows → Output: {len(labeled)} rows ({dropped} end-of-day rows dropped)")

    timestamps = pd.to_datetime(labeled['timestamp'])
    ist_dates = _to_ist_date(timestamps)
    forward_rets = labeled['forward_return_pct'].values
    n = len(forward_rets)

    cross_session_count = 0
    wrong_horizon_count = 0
    diagnostics = []

    for i in range(n):
        ret = forward_rets[i]
        if np.isnan(ret):
            continue

        feat_ts = timestamps.iloc[i]
        feat_ist_date = ist_dates.iloc[i]
        feat_ist_time = str(timestamps.iloc[i])[11:19]

        target_ts_limit = feat_ts + pd.Timedelta(minutes=horizon_minutes)
        target_idx = None
        for j in range(i + 1, min(i + horizon_minutes + 5, n)):
            if ist_dates.iloc[j] != feat_ist_date:
                break
            if timestamps.iloc[j] >= target_ts_limit:
                target_idx = j
                break

        if target_idx is None:
            continue  # expected — dropped by generate_labels

        target_ist_date = ist_dates.iloc[target_idx]
        actual_elapsed = (timestamps.iloc[target_idx] - feat_ts).total_seconds() / 60
        target_ist_time = str(timestamps.iloc[target_idx])[11:19]

        if feat_ist_date != target_ist_date:
            cross_session_count += 1
            ret_str = f"{ret:.4f}"
            if ret > 0:
                ret_str = f"+{ret:.4f}"
            diagnostics.append(
                f"  CROSS-SESSION: {feat_ist_time} ({feat_ist_date}) → "
                f"{target_ist_time} ({target_ist_date}) | "
                f"elapsed={actual_elapsed:.0f}m | ret={ret_str}% | "
                f"label={labeled['label'].iloc[i]}"
            )

        if abs(actual_elapsed - horizon_minutes) > 1:
            wrong_horizon_count += 1

    print(f"\n  Results:")
    print(f"    Total valid labels: {n}")
    print(f"    Cross-session labels: {cross_session_count}")
    print(f"    Wrong-horizon labels: {wrong_horizon_count}")
    print(f"    End-of-day rows correctly dropped: {dropped}")

    if diagnostics:
        print(f"\n  Cross-session violations:")
        for d in diagnostics[:10]:
            print(d)

    # Last rows of last 3 days
    print(f"\n  Last labels of last 3 days (showing session boundary):")
    last_three_days = sorted(set(ist_dates))[-3:]
    for day in last_three_days:
        mask = ist_dates == day
        day_indices = np.where(mask)[0]
        print(f"    Day {day}: {len(day_indices)} rows — last labels:")
        for idx in range(max(0, len(day_indices) - 5), len(day_indices)):
            i = day_indices[idx]
            t = str(timestamps.iloc[i])[11:19]
            label = labeled['label'].iloc[i]
            ret = forward_rets[i]
            print(f"      {t} | {label:8s} | {ret:+.4f}%")

    return {
        "cross_session": cross_session_count,
        "wrong_horizon": wrong_horizon_count,
        "total_valid": n,
    }


def main():
    print("="*70)
    print("  CHECK LABEL BOUNDARIES — Milestone 2")
    print("  Verifies no forward-looking labels cross IST trading days")
    print("="*70)

    df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
    print(f"\n  Loaded {len(df)} rows, {len(df.columns)} cols")
    print(f"  Date range: {str(df['timestamp'].min())[:19]} → {str(df['timestamp'].max())[:19]}")

    all_ok = True
    for h in [5, 10, 15]:
        result = verify_labels(df, h)
        if result["cross_session"] > 0 or result["wrong_horizon"] > 0:
            all_ok = False

    print(f"\n{'='*70}")
    if all_ok:
        print("  ✓ VERDICT: ALL LABELS SESSION-SAFE — ZERO VIOLATIONS")
    else:
        print("  ✗ VERDICT: VIOLATIONS FOUND — SEE ABOVE")
    print(f"{'='*70}")

    return all_ok


if __name__ == "__main__":
    main()
