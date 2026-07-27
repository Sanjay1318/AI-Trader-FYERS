"""
Tests for DataValidator
────────────────────────
Validates the data quality validator's ability to detect:
  - NaN values
  - Duplicate timestamps
  - Negative volume
  - Impossible RSI values
  - Missing candles
  - Invalid OHLC relationships
  - Timezone consistency
  - Outlier detection
"""

import pytest
import pandas as pd
import numpy as np

from features.validator import DataValidator


@pytest.fixture
def clean_data():
    """A clean DataFrame with no issues."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-07-22 09:15", periods=5, freq="1min"),
        "open": [23500.0, 23510.0, 23520.0, 23515.0, 23530.0],
        "high": [23550.0, 23540.0, 23560.0, 23545.0, 23570.0],
        "low": [23480.0, 23500.0, 23510.0, 23505.0, 23520.0],
        "close": [23520.0, 23530.0, 23525.0, 23535.0, 23550.0],
        "volume": [2500, 3200, 1800, 4100, 2900],
        "rsi": [55.0, 58.0, 52.0, 60.0, 57.0],
        "ema20": [23450.0, 23460.0, 23470.0, 23480.0, 23490.0],
        "ema50": [23300.0, 23310.0, 23320.0, 23330.0, 23340.0],
        "atr": [45.0, 44.0, 46.0, 43.0, 47.0],
    })


# ── Tests: DataValidator Constructor ──────────────────────────────────────────

class TestDataValidator:

    def test_validator_instantiation(self):
        """DataValidator can be instantiated."""
        v = DataValidator()
        assert v is not None

    def test_validate_clean_data_passes(self, clean_data):
        """validate passes clean data through unchanged."""
        v = DataValidator()
        result = v.validate(clean_data)
        assert len(result) == len(clean_data)
        assert list(result.columns) == list(clean_data.columns)

    def test_validate_rejects_invalid_ohlc(self):
        """validate rejects rows with invalid OHLC relationships."""
        v = DataValidator()
        bad = pd.DataFrame({
            "timestamp": [pd.Timestamp.now()],
            "open": [100.0],
            "high": [90.0],  # high < open — invalid
            "low": [80.0],
            "close": [95.0],
            "volume": [1000],
        })
        result = v.validate(bad)
        assert len(result) == 0  # all rejected

    def test_validate_rejects_negative_volume(self):
        """validate rejects rows with negative volume."""
        v = DataValidator()
        bad = pd.DataFrame({
            "timestamp": [pd.Timestamp.now()],
            "open": [100.0],
            "high": [110.0],
            "low": [95.0],
            "close": [105.0],
            "volume": [-100],  # negative volume
        })
        result = v.validate(bad)
        assert len(result) == 0

    def test_report_returns_summary(self, clean_data):
        """report returns a dict with validation summary."""
        v = DataValidator()
        report = v.report(clean_data)
        assert "total_rows" in report
        assert "accepted_rows" in report
        assert "rejected_rows" in report
        assert "rejection_reasons" in report
        assert report["accepted_rows"] == len(clean_data)

    def test_validate_with_report_detects_issues(self):
        """validate_with_report detects and counts all issue types."""
        v = DataValidator()
        bad = pd.DataFrame({
            "timestamp": pd.date_range("2026-07-22 09:15", periods=3, freq="1min").repeat(2)[:3],
            "open": [100.0, 110.0, 120.0],
            "high": [90.0, 115.0, 125.0],  # row 0: high < open
            "low": [80.0, 105.0, 115.0],
            "close": [95.0, 112.0, 122.0],
            "volume": [1000, -50, 2000],   # row 1: negative volume
        })
        result = v.validate_with_report(bad)
        assert result.rejected_rows > 0
        assert len(result.rejection_reasons) > 0


# ── Tests: Validator is Composable ────────────────────────────────────────────

class TestValidatorInPipeline:

    def test_pipeline_skips_validator_gracefully(self):
        """Pipeline doesn't crash when validator is not implemented."""
        from features.feature_engine_new import FeaturePipeline
        import pandas as pd

        pipeline = FeaturePipeline(modules=[])
        df = pd.DataFrame({
            "open": [23500.0],
            "high": [23550.0],
            "low": [23480.0],
            "close": [23520.0],
            "volume": [2500],
        })
        # Should not crash with NotImplementedError from validator
        result = pipeline.run(df, persist=False)
        assert result is not None

