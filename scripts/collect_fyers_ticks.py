"""Provider-selected FYERS tick ingestion.

This is intentionally separate from the legacy TrueData collector during the
migration.  It uses the same TickCollector, tick_data, minute_candles, and
live-cache contracts, so downstream research and future AI feature pipelines
remain provider-neutral.
"""

from __future__ import annotations

import argparse
import atexit
import json
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import FYERS_LIVE_SYMBOLS, FYERS_STORAGE_SYMBOL_ALIASES
from data.fyers_adapter import FyersMarketDataAdapter
from data.tick_collector import TickCollector
from database.db import get_engine, upsert_candles
from utils.logger import get_logger

logger = get_logger("fyers_collector")

_running = True
_adapter: FyersMarketDataAdapter | None = None
_collector: TickCollector | None = None
_live_prices: dict[str, dict] = {}


def _cache_path() -> Path:
    """Shared provider-neutral cache consumed by the backend's SSE stream."""
    folder = Path("/tmp") if __import__("os").name != "nt" else Path("temp")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "market_live_prices.json"


class MinuteCandleWriter:
    """Finalize each symbol's current minute without provider-specific storage."""

    def __init__(self):
        self._minute: dict[str, datetime] = {}
        self._ticks: dict[str, list[dict]] = {}

    def add(self, tick: dict) -> None:
        symbol, timestamp = tick["symbol"], tick["timestamp"]
        minute = timestamp.replace(second=0, microsecond=0)
        current = self._minute.get(symbol)
        if current is not None and minute > current:
            self._persist(symbol)
        self._minute[symbol] = minute
        self._ticks.setdefault(symbol, []).append(tick)

    def flush(self) -> None:
        for symbol in list(self._ticks):
            self._persist(symbol)

    def _persist(self, symbol: str) -> None:
        ticks = self._ticks.get(symbol, [])
        if not ticks:
            return
        prices = [float(item["price"]) for item in ticks]
        volumes = [int(item.get("volume") or 0) for item in ticks]
        # FYERS reports cumulative session volume.  A minute's traded volume is
        # the non-negative change across observed updates, not the sum of totals.
        minute_volume = max(0, max(volumes) - min(volumes)) if volumes else 0
        candle = {
            "timestamp": self._minute[symbol],
            "symbol": symbol,
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": minute_volume,
            "vwap": sum(prices) / len(prices),
            "oi": int(ticks[-1].get("oi") or 0),
        }
        try:
            upsert_candles(pd.DataFrame([candle]))
            logger.info("Stored FYERS 1m candle: %s %s", symbol, candle["timestamp"])
        except Exception as exc:
            # Stage 3 must not make the live feed fail if an older deployment
            # has tick_data but not yet the minute_candles table (Stage 4).
            logger.warning("FYERS candle generated but not stored: %s", exc)
        self._ticks[symbol] = []


def _write_cache() -> None:
    path = _cache_path()
    while _running:
        try:
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(_live_prices))
            temp.replace(path)
        except Exception as exc:
            logger.debug("Live-price cache write failed: %s", exc)
        time.sleep(1)


def _shutdown(*_args) -> None:
    global _running
    _running = False


def main() -> None:
    global _adapter, _collector
    parser = argparse.ArgumentParser(description="FYERS normalized tick collector")
    parser.add_argument("--test", action="store_true", help="Verify DB and FYERS quote access only")
    parser.add_argument("--duration-seconds", type=int, default=0, help="Stop automatically after N seconds")
    args = parser.parse_args()

    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    _adapter = FyersMarketDataAdapter()
    health = _adapter.health_check()
    if not health.get("connected"):
        raise RuntimeError(f"FYERS provider is unavailable: {health}")
    if args.test:
        quotes = _adapter.get_quotes(FYERS_LIVE_SYMBOLS)
        print(f"FYERS collector preflight: PASS ({len(quotes)} quote(s))")
        return

    _collector = TickCollector(buffer_size=100)
    candles = MinuteCandleWriter()

    def on_tick(market_tick) -> None:
        canonical = FYERS_STORAGE_SYMBOL_ALIASES.get(market_tick.symbol, market_tick.symbol)
        _collector.on_market_tick(market_tick, symbol=canonical)
        tick = {
            "timestamp": market_tick.timestamp or datetime.now(),
            "symbol": canonical,
            "price": market_tick.price,
            "volume": market_tick.volume or 0,
            "bid_price": market_tick.bid_price,
            "ask_price": market_tick.ask_price,
            "oi": market_tick.open_interest,
        }
        candles.add(tick)
        _live_prices[canonical] = {
            "price": tick["price"],
            "bid": tick["bid_price"] or tick["price"],
            "ask": tick["ask_price"] or tick["price"],
            "ts": datetime.now().isoformat(),
        }

    _adapter.start_stream(FYERS_LIVE_SYMBOLS, on_tick)
    threading.Thread(target=_write_cache, name="fyers-live-cache", daemon=True).start()
    started = time.monotonic()
    try:
        while _running and (not args.duration_seconds or time.monotonic() - started < args.duration_seconds):
            time.sleep(0.5)
    finally:
        _adapter.stop_stream()
        _collector.flush()
        candles.flush()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    atexit.register(_shutdown)
    main()
