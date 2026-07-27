"""
Tests for the Feature Engine v2 Pipeline
──────────────────────────────────────────
Tests the feature pipeline orchestration, module interface, and
full end-to-end feature computation flow.
"""

import pytest
import pandas as pd
import numpy as np

from features.feature_base import BaseFeatureModule
from features.feature_engine_new import FeaturePipeline, build_features


# ── Sample Data ───────────────────────────────────────────────────────────────

@pytest.fixture
def sample_candles():
    """Generate 100 minutes of synthetic OHLCV data."""
    np.random.seed(42)
    n = 100
    base = 23500.0
    closes = base + np.cumsum(np.random.randn(n) * 10)
    highs = closes + np.abs(np.random.randn(n) * 5)
    lows = closes - np.abs(np.random.randn(n) * 5)
    opens = closes - np.random.randn(n) * 3
    volumes = np.random.randint(1000, 5000, n)

    timestamps = pd.date_range(
        start="2026-07-22 09:15:00",
        periods=n,
        freq="1min",
        tz="Asia/Kolkata",
    )

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


@pytest.fixture
def invalid_candles():
    """Data with deliberately bad values."""
    return pd.DataFrame({
        "timestamp": [pd.Timestamp.now(tz="Asia/Kolkata")],
        "open": [100.0],
        "high": [90.0],  # high < open — invalid
        "low": [95.0],
        "close": [102.0],
        "volume": [-100],  # negative volume
    })


# ── Tests: Base Module Interface ──────────────────────────────────────────────

class TestBaseFeatureModule:

    def test_module_interface(self):
        """BaseFeatureModule cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseFeatureModule()

    def test_concrete_module(self):
        """A concrete module must implement required_columns and compute."""

        class GoodModule(BaseFeatureModule):
            def required_columns(self):
                return ["close"]

            def compute(self, df):
                df["double_close"] = df["close"] * 2
                return df

        m = GoodModule()
        df = pd.DataFrame({"close": [100.0, 101.0, 102.0]})
        result = m(df)
        assert "double_close" in result.columns
        assert result["double_close"].iloc[0] == 200.0

    def test_validate_input_passes(self):
        """validate_input succeeds when all columns exist."""

        class TestModule(BaseFeatureModule):
            def required_columns(self):
                return ["open", "high", "low", "close", "volume"]

            def compute(self, df):
                return df

        m = TestModule()
        df = pd.DataFrame({
            "open": [1.0], "high": [2.0], "low": [0.5],
            "close": [1.5], "volume": [100],
        })
        # Should not raise
        m.validate_input(df)

    def test_validate_input_fails(self):
        """validate_input raises when columns are missing."""

        class TestModule(BaseFeatureModule):
            def required_columns(self):
                return ["open", "high", "low", "close", "volume"]

            def compute(self, df):
                return df

        m = TestModule()
        df = pd.DataFrame({"open": [1.0], "close": [1.5]})
        with pytest.raises(ValueError, match="missing required columns"):
            m.validate_input(df)


# ── Tests: Feature Pipeline ───────────────────────────────────────────────────

class TestFeaturePipeline:

    def test_pipeline_requires_ohlcv(self, sample_candles):
        """Pipeline raises on missing required columns."""
        pipeline = FeaturePipeline()
        bad_df = sample_candles.drop(columns=["volume"])
        with pytest.raises(ValueError, match="missing required columns"):
            pipeline.run(bad_df, persist=False)

    def test_pipeline_runs_without_modules(self, sample_candles):
        """Pipeline runs even when all modules are unimplemented (graceful skip)."""
        pipeline = FeaturePipeline(modules=[])
        result = pipeline.run(sample_candles, symbol="TEST", persist=False)
        assert result is not None
        assert "symbol" in result.columns
        assert result["symbol"].iloc[0] == "TEST"

    def test_pipeline_passes_through_data(self, sample_candles):
        """Original columns are preserved through the pipeline."""
        pipeline = FeaturePipeline(modules=[])
        result = pipeline.run(sample_candles, persist=False)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns

    def test_build_features_convenience(self, sample_candles):
        """build_features convenience function works."""
        result = build_features(sample_candles, symbol="TEST", persist=False)
        assert result is not None
        assert "symbol" in result.columns

    def test_pipeline_default_modules_list(self):
        """Default module list should be non-empty and ordered correctly."""
        pipeline = FeaturePipeline()
        assert len(pipeline.modules) > 0
        module_names = [m.__class__.__name__ for m in pipeline.modules]
        assert "TechnicalFeatures" in module_names
        assert "VolumeFeatures" in module_names

    def test_pipeline_with_custom_modules(self, sample_candles):
        """Custom module list overrides defaults."""

        class PlusOneModule(BaseFeatureModule):
            def required_columns(self):
                return ["close"]

            def compute(self, df):
                df["close_plus_one"] = df["close"] + 1
                return df

        pipeline = FeaturePipeline(modules=[PlusOneModule()])
        result = pipeline.run(sample_candles, persist=False)
        assert "close_plus_one" in result.columns
        assert result["close_plus_one"].iloc[0] == sample_candles["close"].iloc[0] + 1

    def test_run_with_ticks_no_crash(self, sample_candles):
        """run_with_ticks handles missing tick data gracefully."""
        pipeline = FeaturePipeline()
        result = pipeline.run_with_ticks(sample_candles, tick_df=None, persist=False)
        assert result is not None


# ── Tests: Edge Cases ─────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_dataframe(self):
        """Pipeline handles empty DataFrame gracefully — returns empty result."""
        pipeline = FeaturePipeline()
        empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = pipeline.run(empty_df, persist=False)
        assert result is not None
        assert len(result) == 0

    def test_single_row(self):
        """Pipeline handles single-row DataFrames (with enough rows for indicators)."""
        pipeline = FeaturePipeline()
        # Single valid row with no modules that need warmup
        single = pd.DataFrame({
            "open": [23500.0],
            "high": [23550.0],
            "low": [23480.0],
            "close": [23520.0],
            "volume": [2500],
        })
        result = pipeline.run(single, modules=[], persist=False)
        assert len(result) == 1

    def test_missing_symbol_added(self, sample_candles):
        """Symbol column is added if not present."""
        pipeline = FeaturePipeline(modules=[])
        result = pipeline.run(sample_candles, symbol="NIFTY-I", persist=False)
        assert "symbol" in result.columns
        assert all(result["symbol"] == "NIFTY-I")

    def test_preserves_timestamp(self, sample_candles):
        """Timestamp column is preserved through the pipeline."""
        pipeline = FeaturePipeline(modules=[])
        result = pipeline.run(sample_candles, persist=False)
        assert "timestamp" in result.columns
        assert len(result) > 0  # some rows may be filtered by validator
        # All original columns should be present
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns

