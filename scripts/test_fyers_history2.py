"""
Detailed FYERS History API validation.
Writes structured output to a file for inspection.
"""
import sys, os, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from config.settings import FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN
from fyers_apiv3 import fyersModel

fm = fyersModel.FyersModel(
    client_id=FYERS_CLIENT_ID,
    token=FYERS_ACCESS_TOKEN,
    is_async=False,
    log_path="",
)

out = []

def log(msg):
    out.append(msg)
    print(msg)

# 1. Test single trading day: 2026-07-24 (Friday)
log("=== TEST 1: Single day - 2026-07-24 ===")
resp = fm.history(data={
    "symbol": "NSE:NIFTY50-INDEX",
    "resolution": "1",
    "date_format": "1",
    "range_from": "2026-07-24",
    "range_to": "2026-07-24",
    "cont_flag": "1",
})
c = resp.get("candles", [])
log(f"Status: {resp.get('s')}, Candles: {len(c)}")
if c:
    # Candle format: [epoch, open, high, low, close, volume]
    log(f"Sample candle: {c[0]}")
    log(f"First: epoch={c[0][0]} dt={datetime.fromtimestamp(c[0][0], tz=timezone.utc)}")
    log(f"Last:  epoch={c[-1][0]} dt={datetime.fromtimestamp(c[-1][0], tz=timezone.utc)}")
    
    # Categorize by date
    dates = {}
    for candle in c:
        d = datetime.fromtimestamp(candle[0], tz=timezone.utc).strftime("%Y-%m-%d")
        dates.setdefault(d, 0)
        dates[d] += 1
    log(f"Candles by date: {json.dumps(dates, indent=2)}")
    
    # Check volume
    vol_total = sum(candle[5] for candle in c)
    vol_nonzero = sum(1 for candle in c if candle[5] > 0)
    zero_vol = sum(1 for candle in c if candle[5] == 0)
    log(f"Total volume: {vol_total}")
    log(f"Non-zero volume candles: {vol_nonzero}")
    log(f"Zero volume candles: {zero_vol}")
    log(f"Close range: {min(candle[4] for candle in c):.1f} - {max(candle[4] for candle in c):.1f}")

# 2. Test weekday range: Jul 20 (Mon) - Jul 24 (Fri)
log("\n=== TEST 2: Range Jul 20-24 ===")
resp = fm.history(data={
    "symbol": "NSE:NIFTY50-INDEX",
    "resolution": "1",
    "date_format": "1",
    "range_from": "2026-07-20",
    "range_to": "2026-07-24",
    "cont_flag": "1",
})
c = resp.get("candles", [])
log(f"Candles: {len(c)}")
if c:
    dates = {}
    for candle in c:
        d = datetime.fromtimestamp(candle[0], tz=timezone.utc).strftime("%Y-%m-%d")
        dates.setdefault(d, 0)
        dates[d] += 1
    log(f"Candles by date:")
    for d, cnt in sorted(dates.items()):
        log(f"  {d}: {cnt} candles")
    log(f"First: {datetime.fromtimestamp(c[0][0], tz=timezone.utc)}")
    log(f"Last:  {datetime.fromtimestamp(c[-1][0], tz=timezone.utc)}")

# 3. Test max range: 30 days from today
log("\n=== TEST 3: 30-day range ===")
resp = fm.history(data={
    "symbol": "NSE:NIFTY50-INDEX",
    "resolution": "1",
    "date_format": "1",
    "range_from": "2026-07-01",
    "range_to": "2026-07-24",
    "cont_flag": "1",
})
c = resp.get("candles", [])
log(f"Status: {resp.get('s')}, Candles: {len(c)}")
if c:
    dates = {}
    for candle in c:
        d = datetime.fromtimestamp(candle[0], tz=timezone.utc).strftime("%Y-%m-%d")
        dates.setdefault(d, 0)
        dates[d] += 1
    log(f"Trading days: {len(dates)}")
    for d, cnt in sorted(dates.items()):
        log(f"  {d}: {cnt} candles")

# 4. Try even larger range for 6 months
log("\n=== TEST 4: 6-month range ===")
resp = fm.history(data={
    "symbol": "NSE:NIFTY50-INDEX",
    "resolution": "1",
    "date_format": "1",
    "range_from": "2026-02-01",
    "range_to": "2026-07-24",
    "cont_flag": "1",
})
c = resp.get("candles", [])
log(f"Status: {resp.get('s')}, Candles: {len(c)}")
if c:
    dates = set()
    for candle in c:
        d = datetime.fromtimestamp(candle[0], tz=timezone.utc).strftime("%Y-%m-%d")
        dates.add(d)
    log(f"Unique trading days: {len(dates)}")
    log(f"First: {datetime.fromtimestamp(c[0][0], tz=timezone.utc)}")
    log(f"Last:  {datetime.fromtimestamp(c[-1][0], tz=timezone.utc)}")

# 5. Check cont_flag=0 vs 1 difference
log("\n=== TEST 5: cont_flag=0 vs 1 on single day ===")
resp0 = fm.history(data={
    "symbol": "NSE:NIFTY50-INDEX",
    "resolution": "1",
    "date_format": "1",
    "range_from": "2026-07-24",
    "range_to": "2026-07-24",
    "cont_flag": "0",
})
c0 = resp0.get("candles", [])
resp1 = fm.history(data={
    "symbol": "NSE:NIFTY50-INDEX",
    "resolution": "1",
    "date_format": "1",
    "range_from": "2026-07-24",
    "range_to": "2026-07-24",
    "cont_flag": "1",
})
c1 = resp1.get("candles", [])
log(f"cont_flag=0: {len(c0)} candles")
log(f"cont_flag=1: {len(c1)} candles")

# Save output
output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audit", "fyers_history_test.txt")
with open(output_path, "w") as f:
    f.write("\n".join(out))
print(f"\nResults saved to {output_path}")
