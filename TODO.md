# Feature Set v1.0 — Implementation TODO

## Step 1: Remove SMA20/SMA50
- [x] `features/technical.py` — remove SMA20/SMA50 computation + docstring

## Step 2: Add Derived Relative-Price Features
- [x] `features/technical.py` — add return_1m, return_3m, return_5m, high_low_pct, close_open_pct, body_pct, rolling_volatility

## Step 3: Add log_volume to Volume Features
- [x] `features/volume.py` — add log_volume = np.log1p(volume)

## Step 4: Rename & Add Market Context Features
- [x] `features/market.py` — rename day_range→day_range_pct, dist_from_high_pct→dist_from_day_high_pct, dist_from_low_pct→dist_from_day_low_pct
- [x] `features/market.py` — ensure all required columns are computed (minutes_since_open, session_progress, day_of_week, gap_pct, gap_type, or_high, or_low, or_breakout_pct, day_high, day_low, day_range_pct, dist_from_day_high_pct, dist_from_day_low_pct)

## Step 5: Update DB Schema (feature_store.py)
- [x] `features/feature_store.py` — add new columns to MARKET_COLUMNS, TECHNICAL_COLUMNS, VOLUME_COLUMNS
- [x] `features/feature_store.py` — expand CREATE_TABLE_SQL with new columns
- [x] `features/feature_store.py` — update ALL_COLUMNS

## Step 6: Update Dataset Builder
- [x] `datasets/dataset_builder.py` — update NUMERIC_FEATURES list (removed sma20/sma50, added new features)

## Step 7: Rebuild Features
- [ ] Run `python scripts/build_features.py --all` to regenerate market_features
- [ ] Run `python scripts/backfill_features.py` to fill in the past data with new columns

## Step 8: Re-run ML Audit
- [ ] Run `python audit/ml_pipeline_audit.py` to validate

## Step 9: Freeze Feature Set
- [ ] Create `docs/FEATURE_SET_V1.md` with final feature list
