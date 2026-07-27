"""Live state check — runs pipeline_debug inline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from config.settings import MARKET_DATA_PROVIDER

print("=" * 60)
print("LIVE STATE CHECK")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Provider: {MARKET_DATA_PROVIDER}")
print("=" * 60)

from database.db import read_sql

today = datetime.now().date().isoformat()

# Q1: How many NIFTY-I minute candles do we have?
print("\n[Q1] minute_candles count:")
df = read_sql("SELECT COUNT(*) as cnt FROM minute_candles WHERE symbol = 'NIFTY-I'", {})
total = int(df.iloc[0]["cnt"]) if not df.empty else 0
print(f"  Total NIFTY-I candles: {total}")

df_today = read_sql("SELECT COUNT(*) as cnt FROM minute_candles WHERE symbol = 'NIFTY-I' AND timestamp::date = :dt", {"dt": today})
today_c = int(df_today.iloc[0]["cnt"]) if not df_today.empty else 0
print(f"  Today ({today}): {today_c} candles")

df_range = read_sql("SELECT MIN(timestamp) as first, MAX(timestamp) as last FROM minute_candles WHERE symbol = 'NIFTY-I'", {})
if not df_range.empty:
    print(f"  Range: {df_range.iloc[0]['first']} -> {df_range.iloc[0]['last']}")

# Q2: Tick data state
print("\n[Q2] tick_data count:")
df_t = read_sql("SELECT COUNT(*) as cnt FROM tick_data WHERE timestamp::date = :dt", {"dt": today})
today_ticks = int(df_t.iloc[0]["cnt"]) if not df_t.empty else 0
print(f"  Ticks today ({today}): {today_ticks}")

df_l = read_sql("SELECT timestamp FROM tick_data ORDER BY timestamp DESC LIMIT 1", {})
if not df_l.empty:
    print(f"  Latest tick: {df_l.iloc[0]['timestamp']}")

# Q3: market_features state
print("\n[Q3] market_features table:")
try:
    df_m = read_sql("SELECT COUNT(*) as cnt FROM market_features", {})
    total_feat = int(df_m.iloc[0]["cnt"]) if not df_m.empty else 0
    print(f"  Total feature rows: {total_feat}")
    df_mr = read_sql("SELECT timestamp, symbol FROM market_features ORDER BY timestamp DESC LIMIT 3", {})
    if not df_mr.empty:
        for _, r in df_mr.iterrows():
            print(f"    {r['timestamp']} | {r['symbol']}")
except Exception as e:
    print(f"  ERROR: {e}")

# Q4: Distinct candle dates
print("\n[Q4] Distinct dates with NIFTY-I candles:")
df_d = read_sql("SELECT DISTINCT timestamp::date as day FROM minute_candles WHERE symbol = 'NIFTY-I' ORDER BY day", {})
if not df_d.empty:
    for _, r in df_d.iterrows():
        print(f"  {r['day']}")

# Q5: Model state
print("\n[Q5] ML Model state:")
for path in ["models/saved/macro_model.pkl", "models/saved/micro_model.pkl"]:
    p = Path(path)
    if p.exists():
        print(f"  {path}: EXISTS ({p.stat().st_size} bytes)")
    else:
        print(f"  {path}: NOT FOUND")

# Q6: FYERS health
print("\n[Q6] FYERS WebSocket health check:")
try:
    from data.fyers_adapter import FyersMarketDataAdapter
    adapter = FyersMarketDataAdapter()
    h = adapter.health_check()
    print(f"  health: {h}")
except Exception as e:
    print(f"  Could not check: {e}")

print("\n" + "=" * 60)
print("CHECK COMPLETE")
print("=" * 60)
