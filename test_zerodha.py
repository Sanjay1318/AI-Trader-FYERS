from kiteconnect import KiteConnect
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('KITE_API_KEY')
api_secret = os.getenv('KITE_API_SECRET')

print("Testing Zerodha Connection...")

try:
    kite = KiteConnect(api_key=api_key)
    print(f"✅ Zerodha API initialized")
    print(f"Login URL: {kite.login_url()}")
    
except Exception as e:
    print(f"❌ Error: {e}")