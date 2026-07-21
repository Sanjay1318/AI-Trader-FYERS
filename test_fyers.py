from dotenv import load_dotenv
from fyers_apiv3 import fyersModel
import os

load_dotenv()

client_id = os.getenv("FYERS_CLIENT_ID")
access_token = os.getenv("FYERS_ACCESS_TOKEN")

if not client_id or not access_token:
    raise ValueError("FYERS_CLIENT_ID or FYERS_ACCESS_TOKEN is missing from .env")

fyers = fyersModel.FyersModel(
    client_id=client_id,
    token=access_token,
    is_async=False,
    log_path=""
)

# Test 1: Verify authentication
print("Profile:")
print(fyers.get_profile())

# Test 2: Get NIFTY 50 LTP
print("\nNIFTY 50 quote:")
print(fyers.quotes(data={
    "symbols": "NSE:NIFTY50-INDEX",
    "data_flag": "1"
}))