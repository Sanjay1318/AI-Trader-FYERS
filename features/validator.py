"""
Data Quality Validator
──────────────────────
Validates feature data before persistence.

Checks implemented:
  - Required columns exist
  - No NaN / infinite values in core columns
  - Volume >= 0
  - High >= Low
  - High >= Open
  - High >= Close
  - Low <= Open
  - Low <= Close
  - RSI between 0–100 (skips NaN warmup rows)
  - ATR >= 0 (skips NaN warmup rows)
  - Timestamps are strictly increasing
  - No duplicate timestamps
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from utils.logger import get_logger

logger = get_logger("validator")


class ValidationResult:
    """Holds validation results including rows rejected and reasons."""

    def __init__(self):
        self.total_rows = 0
        self.rejected_rows = 0
        self.rejection_reasons: Dict[str, int] = {}
        self.cleaned_df: pd.DataFrame = pd.DataFrame()

    @property
    def accepted_rows(self) -> int:
        return self.total_rows - self.rejected_rows

    def summary(self) -> str:
        lines = [
            f"Validation: {self.total_rows} total, "
            f"{self.accepted_rows} accepted, "
            f"{self.rejected_rows} rejected"
        ]
        if self.rejection_reasons:
            lines.append("  Rejections by reason:")
            for reason, count in sorted(
                self.rejection_reasons.items(), key=lambda x: -x[1]
            ):
                lines.append(f"    - {reason}: {count}")
        return "\n".join(lines)


class DataValidator:
    """Validates feature DataFrames for data quality issues."""

    CORE_COLUMNS = ["open", "high", "low", "close", "volume"]

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        self._check_required_columns(df)
        result = self.validate_with_report(df)
        return result.cleaned_df

    def validate_with_report(self, df: pd.DataFrame) -> ValidationResult:
        result = ValidationResult()
        if df.empty:
            return result

        result.total_rows = len(df)
        df = df.copy()
        valid = pd.Series(True, index=df.index)

        self._check_required_columns(df)

        # Check for NaN/Inf in core OHLCV
        for col in self.CORE_COLUMNS:
            col_nan = df[col].isna()
            col_inf = np.isinf(df[col].values) if df[col].dtype.kind in "fc" else pd.Series(False, index=df.index)
            bad = col_nan | col_inf
            if bad.any():
                n_bad = bad.sum()
                valid = valid & ~bad
                result.rejection_reasons[f"NaN/Inf in {col}"] = (
                    result.rejection_reasons.get(f"NaN/Inf in {col}", 0) + n_bad
                )

        # Volume >= 0
        bad_vol = df["volume"] < 0
        if bad_vol.any():
            valid = valid & ~bad_vol
            result.rejection_reasons["Negative volume"] = int(bad_vol.sum())

        # High >= Low
        bad_hl = df["high"] < df["low"]
        if bad_hl.any():
            valid = valid & ~bad_hl
            result.rejection_reasons["High < Low"] = int(bad_hl.sum())

        # High >= Open
        bad_ho = df["high"] < df["open"]
        if bad_ho.any():
            valid = valid & ~bad_ho
            result.rejection_reasons["High < Open"] = int(bad_ho.sum())

        # High >= Close
        bad_hc = df["high"] < df["close"]
        if bad_hc.any():
            valid = valid & ~bad_hc
            result.rejection_reasons["High < Close"] = int(bad_hc.sum())

        # Low <= Open
        bad_lo = df["low"] > df["open"]
        if bad_lo.any():
            valid = valid & ~bad_lo
            result.rejection_reasons["Low > Open"] = int(bad_lo.sum())

        # Low <= Close
        bad_lc = df["low"] > df["close"]
        if bad_lc.any():
            valid = valid & ~bad_lc
            result.rejection_reasons["Low > Close"] = int(bad_lc.sum())

        # RSI between 0-100 (skip NaN warmup rows)
        if "rsi" in df.columns:
            rsi_valid = df["rsi"].notna()
            if rsi_valid.any():
                bad_rsi = (df["rsi"] < 0) | (df["rsi"] > 100)
                bad_rsi = bad_rsi & rsi_valid
                if bad_rsi.any():
                    valid = valid & ~bad_rsi
                    result.rejection_reasons["RSI out of [0, 100]"] = int(bad_rsi.sum())

        # ATR >= 0 (skip NaN warmup rows)
        if "atr" in df.columns:
            atr_valid = df["atr"].notna()
            if atr_valid.any():
                bad_atr = (df["atr"] < 0)
                bad_atr = bad_atr & atr_valid
                if bad_atr.any():
                    valid = valid & ~bad_atr
                    result.rejection_reasons["ATR < 0"] = int(bad_atr.sum())

        # Timestamps strictly increasing
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"])
            non_increasing = ts.diff().dt.total_seconds() <= 0
            non_increasing.iloc[0] = False
            if non_increasing.any():
                valid = valid & ~non_increasing
                result.rejection_reasons["Non-increasing timestamp"] = int(non_increasing.sum())

        # No duplicate timestamps
        if "timestamp" in df.columns:
            dup = df["timestamp"].duplicated(keep="first")
            if dup.any():
                valid = valid & ~dup
                result.rejection_reasons["Duplicate timestamp"] = int(dup.sum())

        result.cleaned_df = df[valid].copy().reset_index(drop=True)
        result.rejected_rows = result.total_rows - len(result.cleaned_df)

        if result.rejected_rows > 0:
            logger.warning(result.summary())
        else:
            logger.info(f"Validation passed: {result.total_rows} rows OK")

        return result

    def report(self, df: pd.DataFrame) -> dict:
        result = self.validate_with_report(df)
        return {
            "total_rows": result.total_rows,
            "accepted_rows": result.accepted_rows,
            "rejected_rows": result.rejected_rows,
            "rejection_reasons": dict(result.rejection_reasons),
            "cleaned_df": result.cleaned_df,
        }

    def _check_required_columns(self, df: pd.DataFrame) -> None:
        missing = [c for c in self.CORE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"DataValidator: missing required columns: {missing}"
            )
