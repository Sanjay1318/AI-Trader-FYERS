"""Debug FYERS WebSocket — test litemode and alternative approaches.

Key finding from REST API:
- NSE:NIFTY50-INDEX returns: lp=23613.3, ask/bid, high/low, volume, atp, tt
- This symbol IS valid

But WebSocket subscribe yields zero data ticks.
Test: litemode=True, different subscription patterns.
"""

import sys, signal, threading, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from config.settings import FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN

_running = True
def _shutdown(*_):
    global _running
    _running = False

def test_litemode():
    """Test with litemode=True — recommended mode for data-only."""
    print("\n" + "=" * 60)
    print("  TEST A: litemode=True, SymbolUpdate")
    print("=" * 60)

    from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket
    ws_token = FYERS_ACCESS_TOKEN if ":" in FYERS_ACCESS_TOKEN else f"{FYERS_CLIENT_ID}:{FYERS_ACCESS_TOKEN}"

    msg_count = [0]
    printed_first = [False]

    def on_connect():
        print("  ✅ on_connect() fired")
        print("  Subscribing to NSE:NIFTY50-INDEX with SymbolUpdate")
        socket.subscribe(symbols=["NSE:NIFTY50-INDEX"], data_type="SymbolUpdate")

    def on_message(msg):
        msg_count[0] += 1
        if msg_count[0] <= 3:
            print(f"\n  --- MESSAGE #{msg_count[0]} ---")
            print(f"  Type: {msg.get('type', 'N/A')}")
            print(f"  Keys: {list(msg.keys())}")
            # Print raw message (truncated)
            raw = json.dumps(msg, default=str)
            print(f"  Full: {raw[:600]}")

    def on_error(e):
        print(f"  ❌ Error: {e}")

    def on_close(m):
        print(f"  Socket closed: {m}")

    socket = FyersDataSocket(
        access_token=ws_token,
        litemode=True,
        write_to_file=False,
        reconnect=True,
        reconnect_retry=2,
        on_connect=on_connect,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    thread = threading.Thread(target=socket.connect, daemon=True)
    thread.start()
    time.sleep(15)

    try:
        socket.close_connection()
    except Exception:
        pass

    print(f"\n  Total messages received: {msg_count[0]}")
    return msg_count[0]


def test_ws_with_ticker():
    """Test with litemode=False but subscribe to ticker symbols via REST."""
    print("\n" + "=" * 60)
    print("  TEST D: Check fyers_api_simple for correct WS pattern")
    print("=" * 60)
    try:
        with open("fyers_api_simple.py") as f:
            content = f.read()
        print(content[:2000])
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    total = test_litemode()
    print(f"\n  With litemode=True: {total} messages in 15s")

    # Check litemode=False control messages (first test)
    print(f"\n  With litemode=False (from earlier test): 2 messages (control only)")

    # Count DB ticks today
    from database.db import read_sql
    today = datetime.now().date().isoformat()
    df = read_sql("SELECT COUNT(*) as cnt FROM tick_data WHERE timestamp::date = :dt", {"dt": today})
    db_ticks = int(df.iloc[0]["cnt"]) if not df.empty else 0
    print(f"\n  DB ticks today ({today}): {db_ticks}")
    print("\n  Done.")
