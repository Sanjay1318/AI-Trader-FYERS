# Feature Store Milestone Tracker

## Milestone 1 ✅ — Foundation & Feature Pipeline
- [x] Folder structure: `features/`, `datasets/`, `training/`, `inference/`, `tests/`
- [x] All `__init__.py` files
- [x] Empty placeholder files (technical.py, volume.py, orderflow.py, volatility.py, market.py, regime.py, validator.py, feature_store.py, dataset_builder.py, labeling.py, predictor.py, ensemble.py, feature_importance.py)
- [x] `feature_base.py` — BaseFeatureModule ABC interface
- [x] `feature_engine_new.py` — Conductor orchestrator with pluggable modules
- [x] `technical.py` — EMA20/50, SMA20/50, RSI, ATR, ADX, DI+/-, MACD
- [x] `volume.py` — VWAP, VWAP dist, Volume SMA20, Relative Volume, OBV
- [x] `market.py` — Session, Gap, Opening Range, Day High/Low/Dist
- [x] `regime.py` — Regime classification (trending_bull/bear, sideways, high/low_vol)
- [x] `validator.py` — Data quality: NaN, OHLC integrity, duplicates, timestamps
- [x] `feature_store.py` — market_features table: create, insert, upsert, load, delete_dupes
- [x] `scripts/build_features.py` — CLI to generate features from historical candles
- [x] `scripts/check_database.py` — DB inspection tool
- [x] `scripts/backfill_features.py` — Backfill missing feature dates
- [x] `scripts/inspect_features.py` — Feature row details
- [x] `tests/test_features.py` — Feature pipeline tests
- [x] `tests/test_validator.py` — Validator tests
- [x] `tests/test_dataset.py` — Dataset builder tests
- [x] `services/feature_sync.py` — Auto-trigger on new candles
- [x] `inference/` modules: base_predictor, rules, scoring, probability, predictor, prediction_store
- [x] `services/prediction_sync.py` — Auto-predict after features

### Pipeline Test Results
- [x] 10,875 candles -> 10,875 feature rows -> 10,875 stored
- [x] 29 trading days (2026-06-15 -> 2026-07-24)
- [x] 44 columns per row (OHLCV + 12 technical + 6 volume + 19 market/regime + meta)
- [x] 4.8% NaN rate (warmup period only)
- [x] 0 duplicates
- [x] Existing scanner/collector/trading untouched

## Milestone 2 ✅ — Label Integrity, ADX Fix & Audits
- [x] ADX Fix — features/technical.py: Replaced broken manual Wilder loop with pandas_ta.adx(). 100% of rows now have non-NaN ADX
- [x] Cross-Session Label Fix — datasets/labeling.py: Labels no longer cross IST trading sessions
- [x] Feature Leakage Audit — 35/35 features PASS (zero future-data leakage)
- [x] Threshold Leakage Audit — thresholds fitted on TRAIN only, frozen for VAL/TEST
- [x] Label Boundaries Audit — zero cross-session, zero wrong-horizon violations
- [x] ML Dataset Audit — 10,534 rows ready for training (31 features, balanced classes)
- [x] AUDIT_REPORT.md — comprehensive audit documentation
- [x] ADX Verification — audit/check_adx.py: 10862/10875 non-NaN ADX

## Milestone 3 — Advanced Features
- [ ] Order Flow tick-derived features (orderflow.py)
- [ ] Volatility: Historical, Realized, Parkinson (volatility.py)
- [ ] Market: Previous day OHLC, Distance from VWAP (market.py)
- [ ] Regime: Bull/Bear/Sideways detection improvements (regime.py)
- [ ] FYERS collector auto-start mechanism

## Milestone 4 — Scanner Integration
- [ ] Wire FeaturePipeline into scan_market()
- [ ] Replace/align with existing feature computation
- [ ] Automated test suite

## Milestone 5 — AI Training Pipeline
- [ ] Dataset builder for ML training
- [ ] Label generation from trade outcomes
- [ ] Training pipeline integration
