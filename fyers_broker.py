from fyers_apiv3 import fyersModel
from dotenv import load_dotenv
import os
import time
from datetime import datetime

load_dotenv()

class FyersBroker:
    def __init__(self):
        self.client_id = os.getenv('FYERS_CLIENT_ID')
        self.access_token = os.getenv('FYERS_ACCESS_TOKEN')
        
        try:
            self.client = fyersModel.FyersClientModel(
                client_id=self.client_id,
                is_async=False,
                token=self.access_token,
                log_path=""
            )
            print("✅ Fyers Client Initialized Successfully")
        except Exception as e:
            print(f"❌ Fyers Init Error: {e}")
    
    def get_live_quote(self, symbols):
        """Get live quotes for symbols"""
        try:
            data = {
                "mode": "LTP",
                "symbols": symbols
            }
            response = self.client.get_quotes(data)
            return response
        except Exception as e:
            print(f"Error fetching quote: {e}")
            return None
    
    def stream_live_data(self, symbols, interval=1):
        """Stream live data every N seconds"""
        print(f"\n🔴 Streaming LIVE DATA from Fyers...")
        print(f"Symbols: {symbols}")
        print(f"Update Interval: {interval} second(s)\n")
        
        while True:
            try:
                quote = self.get_live_quote(symbols)
                
                if quote and 'data' in quote:
                    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
                    
                    for sym, data in quote['data'].items():
                        ltp = data.get('ltp', 0)
                        bid = data.get('bid', 0)
                        ask = data.get('ask', 0)
                        volume = data.get('volume', 0)
                        
                        print(f"  {sym}")
                        print(f"    LTP: {ltp} | Bid: {bid} | Ask: {ask} | Vol: {volume}")
                
                time.sleep(interval)
            
            except KeyboardInterrupt:
                print("\n✅ Stopped streaming")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(interval)

# Test
if __name__ == "__main__":
    broker = FyersBroker()
    
    # Fyers symbol format: "NSE:SBIN-EQ" or "NSE:NIFTY50-INDEX"
    symbols = ["NSE:NIFTY50-INDEX", "NSE:BANKNIFTY-INDEX"]
    
    broker.stream_live_data(symbols, interval=1)