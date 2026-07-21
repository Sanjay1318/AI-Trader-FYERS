from kiteconnect import KiteConnect
from dotenv import load_dotenv
import os
import time
from datetime import datetime

load_dotenv()

class ZerodhaLiveStream:
    def __init__(self):
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        print(f"API Key: {api_key[:10]}***")
        print(f"Access Token: {access_token[:10]}***")
        
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)
    
    def get_live_quote(self, symbols):
        try:
            data = self.kite.quote(symbols)
            return data
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def stream_data(self, symbols, interval=1):
        print(f"\n🔴 Streaming from Zerodha Kite...")
        
        while True:
            try:
                quote = self.get_live_quote(symbols)
                
                if quote and 'data' in quote:
                    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
                    
                    for sym, data in quote['data'].items():
                        ltp = data.get('last_price', 0)
                        bid = data.get('bid', 0)
                        ask = data.get('ask', 0)
                        
                        print(f"  {sym}: LTP={ltp} | Bid={bid} | Ask={ask}")
                
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n\n✅ Stopped streaming")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    streamer = ZerodhaLiveStream()
    streamer.stream_data(["NSE:SBIN", "NSE:NIFTY 50"], interval=1)