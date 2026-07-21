from fyers_apiv3 import fyersModel
from dotenv import load_dotenv
import os

load_dotenv()

app_id = os.getenv('FYERS_CLIENT_ID')  # Your App ID
app_secret = os.getenv('FYERS_APP_SECRET')  # Your App Secret

# Get login URL
fyers = fyersModel.FyersClientModel(client_id=app_id)
login_url = fyers.get_login_url()

print(f"\n🔗 Login URL:\n{login_url}")
print("\nOpen this URL in browser, login to Fyers")
print("You'll get redirected - copy the access token from URL\n")

# User will get auth_code after login
auth_code = input("Enter AUTH CODE from redirect URL: ")

try:
    # Generate session with auth code
    session = fyers.generate_token(app_secret, auth_code)
    access_token = session['access_token']
    
    print(f"\n✅ Access Token Generated!")
    print(f"Token: {access_token}\n")
    
    # Save to .env
    with open('.env', 'a') as f:
        f.write(f"\nFYERS_ACCESS_TOKEN={access_token}")
    
    print("✅ Saved to .env")
    
except Exception as e:
    print(f"❌ Error: {e}")