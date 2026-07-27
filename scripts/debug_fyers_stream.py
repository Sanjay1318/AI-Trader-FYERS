"""Debug FYERS WebSocket: show raw message structure and test symbol formats.

Key observations from first diagnostic:
- WebSocket connects successfully
- Subscribe() works
- Messages arrive (~2.5/sec)
- BUT all messages have price=0, symbol="unknown"
- These are CONTROL messages, not actual tick data

This script adds:
1. Raw message dump (first 10 messages)
2. Control message vs data tick classification
3. Tests different symbol formats (with/without NSE: prefix)
4. Tests different data_type values
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import signal
import threading
import time
from datetime import datetime

from config.settings import FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN, FYERS_LIVE_SYMBOLS

_running = True
_control_count = 0
_data_count = 0


def _shutdown(*_):
    global _running
    _running = False


def inspect_message(msg: dict, label: str = ""):
    """Print the FULL raw message structure."""
    print(f"\n  --- Message {label} ---")
    print(f"  Type: {msg.get('type', 'N/A')}")
    print(f"  Keys: {list(msg.keys())}")
    v = msg.get("v", {})
    if isinstance(v, dict):
        print(f"  v keys: {list(v.keys())}")
        print(f"  v.symbol: {v.get('symbol', 'N/A')}")
        print(f"  v.ltp: {v.get('ltp', v.get('lp', 'N/A'))}")
        print(f"  v.last_traded_time: {v.get('last_traded_time', v.get('tt', 'N/A'))}")
    elif isinstance(v, str):
        print(f"  v (str): {v[:200]}")
    # Show first 500 chars of the full message
    print(f"  Full: {json.dumps(msg, default=str)[:500]}")


def try_stream(
    symbols_to_try,
    data_type="SymbolUpdate",
    label="default",
    timeout=20,
):
    """
    Start a FYERS WebSocket and report raw message structure.

    Args:
        symbols_to_try: List of symbol strings to subscribe to
        data_type: FYERS data_type parameter
        label: Test label for output
        timeout: Max seconds to run
    """
    global _control_count, _data_count
    _control_count = 0
    _data_count = 0

    print(f"\n{'='*60}")
    print(f"  TEST: {label}")
    print(f"  Symbols: {symbols_to_try}")
    print(f"  data_type: {data_type}")
    print(f"{'='*60}")

    from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket

    ws_token = FYERS_ACCESS_TOKEN if ":" in FYERS_ACCESS_TOKEN else f"{FYERS_CLIENT_ID}:{FYERS_ACCESS_TOKEN}"

    first_10_msgs = []
    connect_fired = threading.Event()
    sub_fired = threading.Event()
    msg_received = threading.Event()

    def on_connect():
        connect_fired.set()
        print(f"\n  ✅ on_connect() fired")
        print(f"  Subscribing to: {symbols_to_try}")
        socket.subscribe(symbols=symbols_to_try, data_type=data_type)
        sub_fired.set()

    def on_message(msg):
        global _control_count, _data_count
        msg_received.set()

        # Determine if control or data
        v = msg.get("v", {})
        msg_type = msg.get("type", "")
        has_symbol = bool(v.get("symbol") if isinstance(v, dict) else False)

        if msg_type in ("cn", "ful", "sub", "unsub") and not has_symbol:
            _control_count += 1
        elif msg.get("symbol") or has_symbol:
            _data_count += 1
        else:
            _control_count += 1

        if len(first_10_msgs) < 10:
            first_10_msgs.append(msg)

    def on_error(error):
        print(f"  ❌ Socket error: {error}")

    def on_close(msg):
        print(f"  Socket closed: {msg}")

    socket = FyersDataSocket(
        access_token=ws_token,
        litemode=False,
        write_to_file=False,
        reconnect=True,
        reconnect_retry=2,
        on_connect=on_connect,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    print("  Connecting...")
    thread = threading.Thread(target=socket.connect, daemon=True)
    thread.start()

    connected = connect_fired.wait(timeout=15)
    if not connected:
        print("  ❌ on_connect() NOT fired within 15s")
        print("  FAIL: WebSocket did not connect")
        return socket, "connect_timeout"

    subscribed = sub_fired.wait(timeout=5)
    if not subscribed:
        print("  ❌ subscribe() NOT called within 5s of connect")

    # Wait for any messages
    got_msg = msg_received.wait(timeout=timeout)
    if not got_msg:
        print(f"  ❌ No messages at all in {timeout}s")
        time.sleep(2)

    print(f"\n  --- RESULTS ---")
    print(f"  Control messages: {_control_count}")
    print(f"  Data ticks:       {_data_count}")
    print(f"  Total messages:   {_control_count + _data_count}")

    if first_10_msgs:
        print(f"\n  First {len(first_10_msgs)} raw messages:")
        for i, m in enumerate(first_10_msgs):
            inspect_message(m, f"#{i+1}")

    if _data_count > 0:
        print(f"\n  ✅ DATA TICKS RECEIVED! Streaming pipeline works.")
        result = "data_received"
    elif _control_count > 0:
        print(f"\n  ⚠️  Only control messages. No data ticks.")
        result = "control_only"
    else:
        print(f"\n  ❌ No messages at all.")
        result = "no_messages"

    print(f"  TEST RESULT: {result}")
    return socket, result


def main():
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print("=" * 60)
    print("  FYERS STREAM DEBUGGER")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Test 1: Original config — NSE:NIFTY50-INDEX with SymbolUpdate
    socket1, r1 = try_stream(
        symbols_to_try=sorted(FYERS_LIVE_SYMBOLS),
        data_type="SymbolUpdate",
        label="Test 1: NSE:NIFTY50-INDEX with SymbolUpdate",
        timeout=15,
    )
    try:
        socket1.close_connection()
    except Exception:
        pass
    time.sleep(2)

    # Test 2: Try without NSE: prefix
    raw_symbols = [s.replace("NSE:", "") for s in FYERS_LIVE_SYMBOLS]
    socket2, r2 = try_stream(
        symbols_to_try=raw_symbols,
        data_type="SymbolUpdate",
        label="Test 2: NIFTY50-INDEX (no NSE: prefix)",
        timeout=15,
    )
    try:
        socket2.close_connection()
    except Exception:
        pass
    time.sleep(2)

    # Test 3: Try dot-separated format used by some FYERS versions
    dot_symbols = ["NSE.NIFTY50-INDEX"]
    socket3, r3 = try_stream(
        symbols_to_try=dot_symbols,
        data_type="SymbolUpdate",
        label="Test 3: NSE.NIFTY50-INDEX (dot notation)",
        timeout=15,
    )
    try:
        socket3.close_connection()
    except Exception:
        pass
    time.sleep(2)

    # Test 4: Try SymbolData instead of SymbolUpdate (alternate FYERS API)
    socket4, r4 = try_stream(
        symbols_to_try=sorted(FYERS_LIVE_SYMBOLS),
        data_type="SymbolData",
        label="Test 4: NSE:NIFTY50-INDEX with SymbolData",
        timeout=15,
    )
    try:
        socket4.close_connection()
    except Exception:
        pass

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Test 1 (NSE:NIFTY50-INDEX + SymbolUpdate): {r1}")
    print(f"  Test 2 (NIFTY50-INDEX + SymbolUpdate):      {r2}")
    print(f"  Test 3 (NSE.NIFTY50-INDEX + SymbolUpdate):  {r3}")
    print(f"  Test 4 (NSE:NIFTY50-INDEX + SymbolData):    {r4}")

    any_data = any(r == "data_received" for r in [r1, r2, r3, r4])
    if any_data:
        print(f"\n  ✅ At least one format works!")
    else:
        print(f"\n  ❌ None worked. Check FYERS API documentation for correct symbol/data_type.")
        print(f"  Possible next steps:")
        print(f"    1. Try 'NSE:NIFTY 50-INDEX' with space (from MarketQuote response)")
        print(f"    2. Try subscribing to 'NSE:NIFTY50-INDEX' with data_flag in SymbolUpdate")
        print(f"    3. Check if FYERS requires full symbol with exchange prefix 'NSE_EQ'")
        print(f"    4. Check if account needs KYC/data subscription activation")

    if _running:
        print(f"\n  Press Ctrl+C to exit.")
        try:
            while _running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
