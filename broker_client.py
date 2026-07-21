from dotenv import load_dotenv
import os
from typing import Dict, List
from datetime import datetime
from config.settings import assert_paper_trading_only

load_dotenv()

class BrokerClient:
    def __init__(self, broker='fyers'):
        self.broker = broker
        
        if broker == 'fyers':
            self._init_fyers()
        elif broker == 'zerodha':
            self._init_zerodha()
    
    def _init_fyers(self):
        """Initialize Fyers client"""
        try:
            from fyers_apiv3 import fyersModel
            self.client = fyersModel.FyersClientModel(
                client_id=os.getenv('FYERS_CLIENT_ID'),
                is_async=False,
                token=os.getenv('FYERS_ACCESS_TOKEN'),
                log_path=""
            )
            print("✅ Fyers Client Initialized")
        except Exception as e:
            print(f"❌ Fyers Init Error: {e}")
    
    def _init_zerodha(self):
        """Initialize Zerodha client"""
        try:
            from kiteconnect import KiteConnect
            self.client = KiteConnect(api_key=os.getenv('KITE_API_KEY'))
            print("✅ Zerodha Client Initialized")
        except Exception as e:
            print(f"❌ Zerodha Init Error: {e}")
    
    def get_live_quote(self, symbols: List[str]) -> Dict:
        """Get live data for symbols"""
        try:
            if self.broker == 'fyers':
                data = {
                    "mode": "LTP",
                    "symbols": symbols
                }
                response = self.client.get_quotes(data)
                return response
            
            elif self.broker == 'zerodha':
                response = self.client.quote(symbols)
                return response
        
        except Exception as e:
            print(f"Error fetching live quote: {e}")
            return None
    
    def get_orderbook(self):
        """Get all open orders"""
        try:
            if self.broker == 'fyers':
                return self.client.get_orderbook()
            elif self.broker == 'zerodha':
                return self.client.orders()
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
            return None
    
    def place_order(self, symbol, qty, price, side, order_type='LIMIT'):
        """Block real broker orders while the project is in paper-only mode."""
        assert_paper_trading_only()
        raise RuntimeError(
            "BrokerClient cannot submit real orders during the FYERS migration. "
            "Use the paper-trading adapter for simulated fills."
        )

# Usage Example
if __name__ == "__main__":
    broker = BrokerClient(broker='fyers')
    
    # Get live quote
    symbols = [os.getenv('NIFTY_SYMBOL')]
    quote = broker.get_live_quote(symbols)
    print(f"\n📊 Live Data:")
    print(quote)
