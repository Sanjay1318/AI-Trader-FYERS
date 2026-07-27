"""
Pipeline Debug Script
─────────────────────
Answers five explicit questions about the data pipeline state.
Do NOT modify. Run with: python scripts/pipeline_debug.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from config.settings import MARKET_DATA_PROVIDER

print("=" * 60)
print("PIPELINE DEBUG REPORT")
print(f"Time: {datetime.now()}")
print(f"Provider: {MARKET_DATA_PROVIDER}")
print("=" * 60)

# Q1: Is the FYERS WebSocket connected?
print("\n[Q1] FYERS WebSocket connected?")
try:
    from data.fyers_adapter import FyersMarketDataAdapter
    adapter = FyersMarketDataAdapter()
    health = adapter.health_check()
    print(f"  health_check(): {health}")
    connected = health.get("connected", False)
    print(f"  -> {'YES' if connected else 'NO'}")
except Exception as e:
    print(f"  ERROR: {e}")
    print(f"  -> NO")

# Q2: Are live ticks being received?
print("\n[Q2] Live ticks being received?")
from database.db import read_sql
today = datetime.now().date().isoformat()
df = read_sql("SELECT COUNT(*) as cnt FROM tick_data WHERE timestamp::date = :dt", {"dt": today})
today_ticks = int(df.iloc[0]["cnt"]) if not df.empty else 0
print(f"  Ticks today ({today}): {today_ticks}")
df2 = read_sql("SELECT timestamp FROM tick_data ORDER BY timestamp DESC LIMIT 1")
if not df2.empty:
latest_ts = df2.iloc[0]['timestamp']
    print(f"  Latest tick: {latest_ts}")
print(f"  -> {'YES' if today_ticks > 0 else 'NO'}")

# Q3: Is minute_candles getting new rows?
print("\n[Q3] minute_candles getting new rows?")
df3 = read_sql("SELECT COUNT(*) as cnt FROM minute_candles WHERE timestamp::date = :dt", {"dt": today})
today_candles = int(df3.iloc[0]["cnt"]) if not df3.empty else 0
print(f"  Candles today ({today}): {today_candles}")
df3b = read_sql("SELECT timestamp, symbol FROM minute_candles ORDER BY timestamp DESC LIMIT 3")
if not df3b.empty:
    for _, r in df3b.iterrows():
        print(f"    {r['timestamp']} | {r['symbol']}")
print(f"  -> {'YES' if today_candles > 0 else 'NO'}")

# Q4: Is market_features getting new rows?
print("\n[Q4] market_features getting new rows?")
try:
    df4 = read_sql("SELECT COUNT(*) as cnt FROM market_features", {})
    total_features = int(df4.iloc[0]["cnt"]) if not df4.empty else 0
    print(f"  Total features in table: {total_features}")
    df4b = read_sql("SELECT timestamp FROM market_features ORDER BY timestamp DESC LIMIT 3")
    if not df4b.empty:
        for _, r in df4b.iterrows():
            print(f"    {r['timestamp']}")
    if total_features > 0:
        print(f"  -> YES")
    else:
        print(f"  -> NO (table is empty)")
except Exception as e:
    print(f"  ERROR: {e}")
    print(f"  -> NO (table may not exist)")

# Q5: Is prediction_history getting new rows?
print("\n[Q5] prediction_history getting new rows?")
try:
    df5 = read_sql("SELECT COUNT(*) as cnt FROM prediction_history", {})
    total_preds = int(df5.iloc[0]["cnt"]) if not df5.empty else 0
    print(f"  Total predictions in table: {total_preds}")
    df5b = read_sql("SELECT id, created_at FROM prediction_history ORDER BY created_at DESC LIMIT 3")
    if not df5b.empty:
        for _, r in df5b.iterrows():
            print(f"    id={r['id']} | {r['created_at']}")
    if total_preds > 0:
        print(f"  -> YES")
    else:
        print(f"  -> NO (table is empty)")
except Exception as e:
    print(f"  ERROR: {e}")
    print(f"  -> NO (table may not exist)")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print(f"  Q1 - FYERS WebSocket connected:     CHECK ABOVE for health_check() output")
print(f"  Q2 - Live ticks being received:     {'YES' if today_ticks > 0 else 'NO'}")
print(f"  Q3 - New minute_candles rows:       {'YES' if today_candles > 0 else 'NO'}")
print(f"  Q4 - New market_features rows:      CHECK ABOVE")
print(f"  Q5 - New prediction_history rows:   CHECK ABOVE")
print("=" * 60)
