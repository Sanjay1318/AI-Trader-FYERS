# 2026-07-26 Milestone 2 Audit Report

## E. Milestones 1-2 Audit Status

### ✅ Fixed: ADX Computation (2026-07-26)

**Root cause**: ADX computation in `features/technical.py` uses a Wilder's RS loop, but the initial `rolling().mean()` for the first ATR row produces a scalar (not a Series), causing the manual Wilder loop to produce all-NaN ADX.

**Fix implemented**: Replaced the manual Wilder loop with `pandas_ta.adx()` which handles the recursive smoothing correctly.

**Verification**: `audit/check_adx.py` confirms 100% of rows now have non-NaN ADX.

---

### ✅ Fixed: Cross-Session Label Boundaries (2026-07-26)

**Root cause**: `datasets/labeling.generate_labels()` searched for forward-return targets across all timestamps linearly, without enforcing IST session boundaries. The last 5-15 candles of each day found their target on the next trading day's opening.

**Fix implemented**: Added `_to_ist_date()` helper and modified the target search loop to stop when the IST date changes. End-of-day rows without within-session targets are dropped (returned as NaN label).

**Test results** (across 29 trading days, 10,875 candles):

| Horizon | Input Rows | Labeled Rows | Dropped (EOD) | Cross-Session | Wrong Horizon |
|---------|-----------|-------------|---------------|---------------|---------------|
| 5m      | 10,875    | 10,730      | 145           | **0** ✅      | **0** ✅      |
| 10m     | 10,875    | 10,585      | 290           | **0** ✅      | **0** ✅      |
| 15m     | 10,875    | 10,440      | 435           | **0** ✅      | **0** ✅      |

---

## F. Completed Audits (2026-07-26)

### ✅ Feature Leakage Audit — `audit/feature_leakage_audit.py`
**Result: 35/35 features PASS — zero future-data leakage**

Audited 35 features for leakage categories:
- Uses negative shift? (future data): All PASS
- Uses centered rolling? (future data): All PASS
- Uses bfill/backfill? (future data): All PASS
- Uses future timestamp?: All PASS
- Uses full-day info? (timestamp-invariant): All PASS

Key findings:
- `day_high`/`day_low` use `cummax()`/`cummin()` (expanding within IST date — only up to row T)
- `gap_pct` uses `ffill` from first-bar-of-day value (computed at T, safe)
- All EMAs/RSI/ATR/MACD use trailing windows only
- No feature uses `shift(-N)`, `center=True`, or full-day statistics

### ✅ Threshold Leakage Audit — `audit/check_threshold_leakage.py`
**Result: Thresholds fitted on TRAIN only, frozen for VAL/TEST**

| Horizon | Train P33 (DOWN) | Train P67 (UP) | Test UP% | Test DOWN% | Test NEUTRAL% |
|---------|-----------------|----------------|----------|------------|---------------|
| 5m      | -0.0196%        | +0.0191%       | 32.6%    | 34.6%      | 32.8%         |
| 10m     | -0.0262%        | +0.0259%       | 31.4%    | 36.4%      | 32.2%         |
| 15m     | -0.0322%        | +0.0340%       | 30.4%    | 35.7%      | 33.9%         |

All validation/test labels use frozen train thresholds — no data leakage.

### ✅ ML Dataset Audit — `audit/ml_dataset_audit.py`
**Result: READY FOR TRAINING**

- 10,534 rows after NaN filtering
- 31 feature columns after one-hot encoding
- Balanced classes: UP=33.0%, DOWN=33.0%, NEUTRAL=34.0%
- Chronological split: Train 20d / Val 4d / Test 5d
- 25 PASS / 0 FAIL on leakage audit

### ✅ ADX Verification — `audit/check_adx.py`
**Result: 100% non-NaN ADX across 10,862 rows**

---

## G. Remaining Issues

### Open: FYERS Collector Auto-Start

| Issue | Detail |
|-------|--------|
| `collect_fyers_ticks.py` | Never auto-started during 09:15-15:30 IST |
| No deployment trigger | No Windows Task Scheduler / no background keeper thread |
| Previous TrueData collector | Used a different mechanism (`_ensure_collector()` in `app.py` checks for TrueData only) |

**Fix needed**: Add a `_ensure_fyers_collector()` that runs in a background thread (similar to `_ensure_collector()` but for the FYERS scripts).

---

## H. Next Steps

1. ✅ Complete backfill
2. ✅ Validate backfilled data quality
3. ✅ Fix ADX computation — verified with `audit/check_adx.py`
4. ✅ Fix label session boundaries — verified with `audit/check_label_boundaries.py`
5. ✅ Implement `build_features.py` CLI
6. ✅ Run FeaturePipeline across all historical data
7. ✅ Report feature quality (NaN %, warmup behavior, indicator availability)
8. ✅ Design ML labels and training methodology
9. ✅ Feature Leakage Audit — 35/35 PASS
10. ✅ Threshold Leakage Audit — thresholds frozen from TRAIN
11. ✅ Label Boundaries Audit — zero cross-session violations
12. ✅ ML Dataset Audit — ready for training
13. ⬜ FYERS collector auto-start mechanism
14. ⬜ Expand indicator set for Milestone 3
