from kiteconnect import KiteConnect
from dotenv import load_dotenv
import os

load_dotenv()

kite = KiteConnect(api_key=os.getenv('KITE_API_KEY'))

# Generate login URL
login_url = kite.login_url()
print(f"\n🔗 Login URL:\n{login_url}")
print("\n1. Open the URL above in your browser")
print("2. Login with your Zerodha account")
print("3. After login, you'll see a blank page with a URL")
print("4. Copy the 'request_token' from that URL")
print("5. Paste it below\n")

# Manually input request token
request_token = input("Enter REQUEST TOKEN: ")

try:
    # Generate session (access token)
    session = kite.generate_session(
        request_token, 
        api_secret=os.getenv('KITE_API_SECRET')
    )
    
    access_token = session['access_token']
    print(f"\n✅ Access Token Generated!")
    print(f"Token: {access_token}\n")
    
    # Update .env
    with open('.env', 'r') as f:
        content = f.read()
    
    # Replace the placeholder
    content = content.replace(
        'KITE_ACCESS_TOKEN=your_kite_access_token_here',
        f'KITE_ACCESS_TOKEN={access_token}'
    )
    
    with open('.env', 'w') as f:
        f.write(content)
    
    print("✅ Saved to .env file!")
    print(f"KITE_ACCESS_TOKEN={access_token}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("Make sure you copied the request_token correctly")