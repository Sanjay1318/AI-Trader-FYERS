import requests
from dotenv import load_dotenv
import os
import time
from datetime import datetime

load_dotenv()

class FyersAPI:
    def __init__(self):
        self.base_url = "https://api-t1.fyers.in/api/v3"
        self.client_id = os.getenv('FYERS_CLIENT_ID')
        self.access_token = os.getenv('FYERS_ACCESS_TOKEN')
    
    def get_quote(self, symbols):
        """Get live quote via REST API (no compilation)"""
        try:
            headers = {
                "Authorization": f"{self.client_id}:{self.access_token}",
                "Accept": "application/json"
            }
            
            params = {
                "symbols": ",".join(symbols),
                "mode": "LTP"
            }
            
            response = requests.get(
                f"{self.base_url}/quotes/",
                headers=headers,
                params=params
            )
            
            return response.json()
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def stream_live(self, symbols, interval=1):
        """Stream live data"""
        print(f"🔴 Streaming from Fyers REST API...")
        
        while True:
            try:
                quote = self.get_quote(symbols)
                
                if quote:
                    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
                    print(f"Response: {quote}\n")
                
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n✅ Stopped")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    api = FyersAPI()
    api.stream_live(["NSE:NIFTY50-INDEX"])