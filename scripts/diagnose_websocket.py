"""Diagnose FYERS WebSocket Streaming Pipeline — Step-by-Step Audit.

Timeline:
  Collector started
  ↓
  Socket created (FyersDataSocket)
  ↓
  Socket connected (on_connect)
  ↓
  Subscribed (subscribe called with symbols)
  ↓
  First tick received (on_message)
  ↓
  Tick persisted
  ↓
  Minutes pass → candle flushed
  ↓
  Features updated

Every stage prints PASS or FAIL with a reason.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import signal
import threading
import time
from datetime import datetime

from config.settings import FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN, FYERS_LIVE_SYMBOLS, FYERS_STORAGE_SYMBOL_ALIASES
from database.db import engine, get_connection
from data.market_data_provider import MarketTick
from utils.logger import get_logger

logger = get_logger("ws_diagnose")

# ── Global state ──────────────────────────────────────────────────────────────

_results = {
    "stage_1_socket_created": {"status": "PENDING", "detail": ""},
    "stage_2_on_connect": {"status": "PENDING", "detail": ""},
    "stage_3_subscribe_called": {"status": "PENDING", "detail": ""},
    "stage_4_first_tick": {"status": "PENDING", "detail": ""},
    "stage_5_ticks_persisted": {"status": "PENDING", "detail": ""},
    "stage_6_minutes_elapsed": {"status": "PENDING", "detail": ""},
}
_running = True
_tick_count = 0
_start_time = time.monotonic()


def _shutdown(*_):
    global _running
    _running = False


def print_result(stage, status, detail=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏳"
    print(f"  {icon} {stage}: {status}  {detail}")
    _results[stage] = {"status": status, "detail": detail}


def main():
    global _tick_count
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print("=" * 60)
    print("  FYERS WEBSOCKET STREAMING PIPELINE DIAGNOSTIC")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Client:  {FYERS_CLIENT_ID}")
    print(f"  Token:   {'SET (length=' + str(len(FYERS_ACCESS_TOKEN)) + ')' if FYERS_ACCESS_TOKEN else 'NOT SET'}")
    print(f"  Symbols: {FYERS_LIVE_SYMBOLS}")
    print("=" * 60)

    # ── Prerequisites check ──────────────────────────────────────────────────

    print("\n[PREREQ] Database reachable?")
    try:
        with get_connection() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        print_result("stage_db", "PASS", "Database connection OK")
    except Exception as e:
        print_result("stage_db", "FAIL", f"Database error: {e}")
        return

    # ── Stage 1: Create WebSocket connection ─────────────────────────────────

    print("\n[STAGE 1] Creating FyersDataSocket...")
    try:
        from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket
    except ImportError as e:
        print_result("stage_1_socket_created", "FAIL", f"Cannot import FyersDataSocket: {e}")
        return

    # Build the access token in websocket format
    ws_token = FYERS_ACCESS_TOKEN if ":" in FYERS_ACCESS_TOKEN else f"{FYERS_CLIENT_ID}:{FYERS_ACCESS_TOKEN}"

    socket_connected = threading.Event()
    tick_received = threading.Event()
    subscribe_called = threading.Event()

    def on_connect():
        socket_connected.set()
        print_result("stage_2_on_connect", "PASS", "on_connect() was invoked")
        print("  Subscribing to symbols now...")
        socket.subscribe(symbols=sorted(FYERS_LIVE_SYMBOLS), data_type="SymbolUpdate")
        subscribe_called.set()
        print_result("stage_3_subscribe_called", "PASS", f"subscribe() called with {list(FYERS_LIVE_SYMBOLS)}")

    def on_message(message):
        global _tick_count
        _tick_count += 1
        if _tick_count == 1:
            tick_received.set()
            print_result("stage_4_first_tick", "PASS", "First tick received via on_message()")

        # Extract symbol and price
        values = message.get("v", message)
        sym = values.get("symbol") or message.get("symbol") or message.get("n", "unknown")
        price = values.get("ltp", values.get("lp", 0))
        ts = values.get("last_traded_time") or values.get("tt", "N/A")

        if _tick_count <= 3:
            print(f"    Tick #{_tick_count}: {sym} price={price} ts={ts}")

    def on_error(error):
        print_result("stage_1_socket_created", "FAIL", f"Socket error during creation: {error}")

    def on_close(message):
        print(f"  Socket close event: {message}")

    print("  Building FyersDataSocket...")
    socket = FyersDataSocket(
        access_token=ws_token,
        litemode=False,
        write_to_file=False,
        reconnect=True,
        reconnect_retry=3,
        on_connect=on_connect,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    print_result("stage_1_socket_created", "PASS", "FyersDataSocket object created")

    # ── Stage 2: Connect ─────────────────────────────────────────────────────

    print("\n[STAGE 2] Connecting socket...")
    print("  Calling socket.connect() in daemon thread...")
    socket_thread = threading.Thread(
        target=socket.connect,
        name="fyers-diag-ws",
        daemon=True,
    )
    socket_thread.start()

    # Wait up to 15 seconds for connection
    print("  Waiting up to 15s for on_connect()...")
    connected = socket_connected.wait(timeout=15)

    if not connected:
        print_result("stage_2_on_connect", "FAIL", "on_connect() NOT called within 15s — socket failed to connect")
        # Try to collect more info
        time.sleep(2)
        print("  Thread alive:", socket_thread.is_alive())
        return

    # ── Stage 3: Verify subscription ─────────────────────────────────────────

    subscribed = subscribe_called.wait(timeout=10)
    if not subscribed:
        print_result("stage_3_subscribe_called", "FAIL", "subscribe() was never called — on_connect() may not have fired subscribe logic")

    # ── Stage 4: Wait for first tick ─────────────────────────────────────────

    print(f"\n[STAGE 4] Waiting up to 30s for first tick...")
    got_tick = tick_received.wait(timeout=30)

    if not got_tick:
        print_result("stage_4_first_tick", "FAIL", "No tick received within 30s after subscribe()")
        elapsed = time.monotonic() - _start_time
        print(f"  Elapsed: {elapsed:.1f}s")
        print("  Possible causes:")
        print("    1. FYERS symbol name is wrong — NSE:NIFTY50-INDEX may differ from actual feed symbol")
        print("    2. Market may be closed / outside trading hours")
        print("    3. FYERS may throttle new WebSocket connections")
        print("    4. The data_type='SymbolUpdate' may be wrong — try 'symbolData' or 'SymbolData'")
        return

    # ── Stage 5: Collect ticks for a bit, verify DB persistence ──────────────

    print(f"\n[STAGE 5] Collecting ticks for 10s to verify persistence...")
    time.sleep(10)
    print(f"  Ticks received so far: {_tick_count}")

    # Check DB
    try:
        today = datetime.now().date().isoformat()
        with get_connection() as conn:
            result = conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT COUNT(*) as cnt FROM tick_data WHERE timestamp::date = :dt"
                ),
                {"dt": today},
            )
            row = result.fetchone()
            db_ticks = row[0] if row else 0

        if db_ticks > 0:
            print_result("stage_5_ticks_persisted", "PASS", f"{db_ticks} ticks in DB today")
        else:
            print_result("stage_5_ticks_persisted", "FAIL", "0 ticks in DB — TickCollector may not be persisting")
    except Exception as e:
        print_result("stage_5_ticks_persisted", "FAIL", f"DB query failed: {e}")

    # ── Final Report ─────────────────────────────────────────────────────────

    elapsed = time.monotonic() - _start_time
    print(f"\n{'='*60}")
    print(f"  DIAGNOSTIC SUMMARY")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Ticks received: {_tick_count}")
    print(f"{'='*60}")

    all_pass = all(
        v["status"] == "PASS" for k, v in _results.items()
        if k.startswith("stage_")
    )
    print(f"\n  Overall: {'✅ ALL PASS' if all_pass else '❌ SOME FAILED'}")
    print()

    # Keep running for a bit so user can see output
    print("  Collector will stay alive for 60s. Press Ctrl+C to exit early.")
    socket_keepalive = 60
    for i in range(socket_keepalive):
        if not _running:
            break
        time.sleep(1)
        if i % 10 == 0 and _tick_count > 0:
            print(f"  [{i+1}s] Ticks so far: {_tick_count}")

    # Cleanup
    try:
        socket.close_connection()
    except Exception:
        pass
    print("\n  Diagnostic complete.")


if __name__ == "__main__":
    main()
