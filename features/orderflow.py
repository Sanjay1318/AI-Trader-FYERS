"""
Order Flow Features Module
───────────────────────────
Only tick-derived features live here.

Features:
  - Bid Ask Ratio
  - Spread
  - Delta (buy volume - sell volume)
  - Order Imbalance
  - Tick Momentum
  - Buying Pressure
  - Selling Pressure

All features are computed on tick-level data and resampled to
one-second bars, then merged to the candle-level pipeline via
the run_with_ticks() entry point.
"""

import numpy as np
import pandas as pd

from features.feature_base import BaseFeatureModule
from utils.logger import get_logger

logger = get_logger("orderflow")


class OrderFlowFeatures(BaseFeatureModule):
    """Computes order-flow / microstructure features from tick-level data."""

    def required_columns(self) -> list:
        return ["bid_price", "ask_price", "bid_qty", "ask_qty", "price", "volume"]

    def compute(self, df):
        """
        Compute order flow features.

        Expects tick-level DataFrame with at least:
            timestamp, price, volume, bid_price, ask_price, bid_qty, ask_qty

        Returns per-second DataFrame with columns:
            bid_ask_ratio, spread, delta, order_imbalance,
            tick_momentum, buying_pressure, selling_pressure

        Also preserves timestamp and symbol for downstream merging.
        """
        df = df.copy()
        df = df.sort_values("timestamp").reset_index(drop=True)

        # ── Spread ────────────────────────────────────────────────────────
        df["spread"] = (df["ask_price"] - df["bid_price"]).clip(lower=0)

        # ── Bid-Ask Ratio ─────────────────────────────────────────────────
        total_qty = df["bid_qty"] + df["ask_qty"]
        df["bid_ask_ratio"] = np.where(
            total_qty > 0,
            df["bid_qty"] / total_qty,
            0.5,  # neutral when no quotes
        )

        # ── Order Imbalance ───────────────────────────────────────────────
        df["order_imbalance"] = np.where(
            total_qty > 0,
            (df["bid_qty"] - df["ask_qty"]) / total_qty,
            0.0,
        )

        # ── Classify trades: buy/sell via tick rule ───────────────────────
        # Price >= ask → buyer-initiated; price <= bid → seller-initiated
        df["is_buy"] = (df["price"] >= df["ask_price"]).astype(int)
        df["is_sell"] = (df["price"] <= df["bid_price"]).astype(int)

        df["buy_volume"] = df["volume"] * df["is_buy"]
        df["sell_volume"] = df["volume"] * df["is_sell"]

        # ── Delta ─────────────────────────────────────────────────────────
        df["delta"] = df["buy_volume"] - df["sell_volume"]

        # ── Buying / Selling Pressure ─────────────────────────────────────
        df["buying_pressure"] = df["buy_volume"].rolling(10, min_periods=1).sum()
        df["selling_pressure"] = df["sell_volume"].rolling(10, min_periods=1).sum()

        # ── Tick Momentum (net order flow over rolling window) ────────────
        df["tick_momentum"] = df["delta"].rolling(10, min_periods=1).sum()
        total_vol_window = df["volume"].rolling(10, min_periods=1).sum()
        df["tick_momentum"] = df["tick_momentum"] / total_vol_window.replace(0, np.nan)

        # ── Keep per-tick result (the engine will downsample as needed) ────
        result_cols = [
            "timestamp", "symbol", "price",
            "bid_ask_ratio", "spread", "delta", "order_imbalance",
            "tick_momentum", "buying_pressure", "selling_pressure",
        ]
        result = df[[c for c in result_cols if c in df.columns]].copy()

        logger.info(f"OrderFlowFeatures: computed {len(result)} tick-level rows")
        return result


# ── Convenience: Downsample order-flow ticks to 1-minute bars ────────────────

def resample_orderflow_to_candles(
    of_df: pd.DataFrame,
    agg_interval: str = "1min",
) -> pd.DataFrame:
    """
    Aggregate per-second order flow data to candle-aligned summaries.

    Args:
        of_df: DataFrame from OrderFlowFeatures.compute() with 'timestamp' column.
        agg_interval: Pandas resample rule (default "1min").

    Returns:
        DataFrame with one row per interval and aggregated order-flow stats.
    """
    if of_df.empty:
        return pd.DataFrame()

    df = of_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    agg = df.resample(agg_interval).agg({
        "symbol": "first",
        "price": "last",
        "bid_ask_ratio": "mean",
        "spread": "mean",
        "delta": "sum",
        "order_imbalance": "mean",
        "tick_momentum": "mean",
        "buying_pressure": "sum",
        "selling_pressure": "sum",
    }).dropna(subset=["symbol"])

    agg = agg.reset_index()
    logger.info(f"Resampled order flow: {len(agg)} {agg_interval} bars")
    return agg

