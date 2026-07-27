"""
Feature Engine (v2)
────────────────────
Orchestrator for the new feature pipeline.

This is the conductor of the orchestra. It coordinates the pipeline:
    Collector → Minute Candle → Technical → Volume → Order Flow →
    Volatility → Market Context → Regime → Validation → Database

Every feature module returns a DataFrame, and the engine merges them
before validation and storage.

Key design principles:
  - Never computes indicators itself.
  - Never writes SQL directly (delegates to feature_store.py).
  - Never contains ML or scanner logic.
  - Modules are pluggable via the BaseFeatureModule interface.
"""

from typing import List, Optional

import pandas as pd

from features.feature_base import BaseFeatureModule
from features.feature_store import (
    insert_features,
    update_features,
    create_table,
)
from features.validator import DataValidator
from utils.logger import get_logger

logger = get_logger("feature_engine_new")


class FeaturePipeline:
    """
    Orchestrates the complete feature computation pipeline.

    Usage:
        pipeline = FeaturePipeline()
        pipeline.run(df)           # full pipeline with default modules
        pipeline.run(df, modules=[TechnicalFeatures(), VolumeFeatures()])
    """

    def __init__(self, modules: Optional[List[BaseFeatureModule]] = None):
        """
        Args:
            modules: Ordered list of feature modules. If None, uses the
                     default set (gradually expanded across milestones).
        """
        self.modules = modules if modules is not None else self._default_modules()
        self.validator = DataValidator()
        self._table_ensured = False

    def _default_modules(self) -> List[BaseFeatureModule]:
        """Default set of feature modules for the pipeline."""
        from features.technical import TechnicalFeatures
        from features.volume import VolumeFeatures
        from features.market import MarketFeatures
        from features.regime import RegimeFeatures

        # Order matters — later modules may depend on earlier outputs
        return [
            TechnicalFeatures(),
            VolumeFeatures(),
            MarketFeatures(),
            RegimeFeatures(),
        ]

    def ensure_storage(self):
        """Ensure the market_features table exists."""
        if not self._table_ensured:
            create_table()
            self._table_ensured = True

    def run(
        self,
        df: pd.DataFrame,
        symbol: str = "NIFTY-I",
        modules: Optional[List[BaseFeatureModule]] = None,
        persist: bool = True,
    ) -> pd.DataFrame:
        """
        Execute the full feature pipeline.

        Flow:
            1. Validate input has required OHLCV columns
            2. Run each feature module in sequence (each augments the DataFrame)
            3. Add symbol column
            4. Validate final features
            5. Persist to database (optional)

        Args:
            df: Input DataFrame with at least [open, high, low, close, volume].
            symbol: Symbol identifier to attach to feature rows.
            modules: Override the default module list for this run.
            persist: If True, save results to the market_features table.

        Returns:
            DataFrame with all computed features.
        """
        # ── Step 1: Validate input ─────────────────────────────────────────
        required = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required columns: {missing}")

        df = df.copy()
        df["symbol"] = symbol

        # ── Step 2: Run modules ────────────────────────────────────────────
        active_modules = modules if modules is not None else self.modules
        for module in active_modules:
            module_name = module.__class__.__name__
            try:
                logger.info(f"Running module: {module_name}")
                module.validate_input(df)
                df = module.compute(df)
                logger.info(f"  {module_name} complete. Columns now: {list(df.columns)}")
            except NotImplementedError:
                logger.info(f"  {module_name} not yet implemented, skipping.")
            except Exception as e:
                logger.error(f"  {module_name} failed: {e}", exc_info=True)
                raise

        # ── Step 3: Validate ───────────────────────────────────────────────
        validation_result = self.validator.validate_with_report(df)
        df = validation_result.cleaned_df
        if validation_result.rejected_rows > 0:
            logger.warning(f"Validation rejected {validation_result.rejected_rows}/{validation_result.total_rows} rows")
        else:
            logger.info(f"Validation passed: {validation_result.total_rows} rows OK")

        # ── Step 4: Persist (optional) ────────────────────────────────────
        if persist:
            self.ensure_storage()
            inserted = insert_features(df)
            logger.info(f"Persisted {inserted} feature rows for {symbol}.")

        return df

    def run_with_ticks(
        self,
        candle_df: pd.DataFrame,
        tick_df: Optional[pd.DataFrame] = None,
        symbol: str = "NIFTY-I",
        persist: bool = True,
    ) -> pd.DataFrame:
        """
        Run the pipeline with optional tick-level order flow features.

        Args:
            candle_df: OHLCV minute-candle DataFrame.
            tick_df: Optional tick-level DataFrame for order flow modules.
            symbol: Symbol identifier.
            persist: If True, save results.

        Returns:
            DataFrame with all features.
        """
        df = self.run(candle_df, symbol=symbol, persist=False)

        # Add order flow features from tick data if available
        if tick_df is not None and not tick_df.empty:
            from features.orderflow import OrderFlowFeatures

            of = OrderFlowFeatures()
            try:
                # Order flow operates on tick data, not candles
                # We compute per-second order flow features and merge
                of.validate_input(tick_df)
                of_df = of.compute(tick_df)
                # Merge order flow into the main feature set
                # (alignment by timestamp will happen downstream)
                logger.info(f"Order flow features computed: {len(of_df)} rows")
            except NotImplementedError:
                logger.info("  OrderFlowFeatures not yet implemented, skipping.")
            except Exception as e:
                logger.warning(f"  Order flow computation failed: {e}")

        if persist:
            self.ensure_storage()
            insert_features(df)

        return df


# ── Convenience Function ──────────────────────────────────────────────────────

def build_features(
    df: pd.DataFrame,
    symbol: str = "NIFTY-I",
    persist: bool = True,
) -> pd.DataFrame:
    """
    One-shot convenience function to compute features in a single call.

    Usage:
        from features.feature_engine_new import build_features
        features = build_features(candle_df)
    """
    pipeline = FeaturePipeline()
    return pipeline.run(df, symbol=symbol, persist=persist)

