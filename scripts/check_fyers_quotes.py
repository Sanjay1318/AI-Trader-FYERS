"""Check what FYERS quotes API returns — to discover actual symbol names."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from datetime import datetime

from config.settings import FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN


def main():
    print("=" * 60)
    print("  FYERS QUOTES API — Symbol Discovery")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    from fyers_apiv3 import fyersModel

    fyers = fyersModel.FyersModel(
        client_id=FYERS_CLIENT_ID,
        token=FYERS_ACCESS_TOKEN,
        is_async=False,
        log_path="",
    )

    # Try multiple symbol formats
    symbols_to_try = [
        "NSE:NIFTY50-INDEX",
        "NSE:NIFTY 50-INDEX",
        "NSE:NIFTY 50",
        "NSE:NIFTY50",
        "NSE:INDEX/NIFTY50",
    ]

    for sym in symbols_to_try:
        try:
            resp = fyers.quotes(data={"symbols": sym})
            print(f"\n  Symbol: {sym}")
            print(f"  Status: {resp.get('s', '?')}")
            d = resp.get("d", [])
            if d:
                item = d[0]
                v = item.get("v", {})
                n = item.get("n", "N/A")
                print(f"  n (name): {n}")
                print(f"  v.keys: {list(v.keys()) if isinstance(v, dict) else type(v)}")
                print(f"  v.lp: {v.get('lp', v.get('ltp', 'N/A'))}")
                print(f"  Full keys: {list(item.keys())}")
                print(f"  Is it v or v has data? ")
                print(f"  Raw (truncated): {json.dumps(item, default=str)[:300]}")
            else:
                print(f"  No data in response")
                print(f"  Full response: {str(resp)[:300]}")
        except Exception as e:
            print(f"  Symbol: {sym}")
            print(f"  ERROR: {e}")

    # Also check the profile for any symbol-related info
    print(f"\n{'='*60}")
    print("  Checking holdings/positions for symbols...")
    try:
        holdings = fyers.holdings()
        print(f"  Holdings: {str(holdings)[:300]}")
    except Exception as e:
        print(f"  Holdings error: {e}")

    try:
        funds = fyers.funds()
        print(f"  Funds: {str(funds)[:300]}")
    except Exception as e:
        print(f"  Funds error: {e}")


if __name__ == "__main__":
    main()
