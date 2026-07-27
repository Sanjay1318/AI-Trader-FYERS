"""
Test FYERS History API systematically.
Writes results to audit/fyers_history_test.txt
"""
import sys, os, json
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

# Test combinations
symbols = [
    "NSE:NIFTY50-INDEX",
    "NSE:NIFTY50-INDICES",
    "NSE:NIFTY_50",
    "NSE:NIFTY-I",
    "NSE:NSE50-INDEX",
    "NSE:NIFTY",
    "MCX:NIFTY",
    "BSE:SENSEX",
]

resolutions = ["1", "5", "15", "60"]
date_formats = [("1", "2026-07-24", "2026-07-24"), ("0", "1721692800", "1721779200")]
# 2026-07-24 00:00:00 UTC = 1721692800 epoch
# 2026-07-24 23:59:59 UTC = 1721779199

results = []

for symbol in symbols:
    for res in resolutions:
        for dfmt, frm, to in date_formats:
            try:
                data = {
                    "symbol": symbol,
                    "resolution": res,
                    "date_format": dfmt,
                    "range_from": frm,
                    "range_to": to,
                    "cont_flag": "1",
                }
                resp = fm.history(data=data)
                n_candles = len(resp.get("candles", []))
                status = resp.get("s", "?")
                msg = resp.get("message", "")
                results.append({
                    "symbol": symbol,
                    "res": res,
                    "dfmt": dfmt,
                    "status": status,
                    "candles": n_candles,
                    "msg": msg,
                })
                if n_candles > 0:
                    # Print first and last candle for inspection
                    ts0 = resp["candles"][0][0]
                    ts1 = resp["candles"][-1][0]
                    print(f"OK: {symbol} res={res} dfmt={dfmt} -> {n_candles}c {ts0}-{ts1}")
            except Exception as e:
                results.append({
                    "symbol": symbol,
                    "res": res,
                    "dfmt": dfmt,
                    "status": "EXCEPTION",
                    "candles": 0,
                    "msg": str(e),
                })

print("\n\n=== SUMMARY ===")
success = [r for r in results if r["candles"] > 0]
print(f"Successful requests: {len(success)}")

for r in success:
    print(f"  {r['symbol']:30s} res={r['res']:3s} dfmt={r['dfmt']} -> {r['candles']:4d} candles")

if not success:
    print("\nNO SUCCESSFUL RESULTS. Full results:")
    for r in results:
        print(f"  {r['symbol']:30s} res={r['res']:3s} -> {r['status']:12s} msg={r['msg']}")

# Also check if quotes work for comparison
try:
    q = fm.quotes(data={"symbols": "NSE:NIFTY50-INDEX"})
    print(f"\n\nQuote check: {json.dumps(q, indent=2)[:500]}")
except Exception as e:
    print(f"\n\nQuote error: {e}")
