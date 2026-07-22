from fyers_apiv3 import fyersModel
from dotenv import load_dotenv
import os
import re
import webbrowser

load_dotenv()

client_id = os.getenv("FYERS_CLIENT_ID")
secret_key = os.getenv("FYERS_APP_SECRET")
redirect_url = "http://localhost:3000/auth"

print("🔐 Fyers OAuth Authentication\n")

try:
    if not client_id or not secret_key:
        raise ValueError("FYERS_CLIENT_ID or FYERS_APP_SECRET is missing from .env")

    # Step 1: Generate the FYERS login URL
    session_model = fyersModel.SessionModel(
        client_id=client_id,
        redirect_uri=redirect_url,
        response_type="code",
        grant_type="authorization_code",
        state="state",
    )

    login_url = session_model.generate_authcode()
    print(f"🔗 Login URL:\n{login_url}\n")

    webbrowser.open(login_url)
    print("✅ Browser opened. Please log in.\n")

    # Copy only the value after auth_code= from the redirected URL
    auth_code = input("Enter AUTH CODE from redirect URL: ").strip()

    # Step 2: Exchange auth_code for access token
    session_model_2 = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        grant_type="authorization_code",
    )

    session_model_2.set_token(auth_code)
    response = session_model_2.generate_token()

    if response and response.get("access_token"):
        access_token = response["access_token"]

        print("\n✅ Access Token Generated!")
        print(f"\nAccess Token:\n{access_token}\n")

        with open(".env", "r", encoding="utf-8") as file:
            content = file.read()

        # Replace the existing access token line
        content = re.sub(
            r"^FYERS_ACCESS_TOKEN=.*$",
            f"FYERS_ACCESS_TOKEN={access_token}",
            content,
            flags=re.MULTILINE,
        )

        with open(".env", "w", encoding="utf-8") as file:
            file.write(content)

        print("✅ Saved to .env!")

    else:
        print(f"❌ FYERS token error: {response}")

except Exception as error:
    print(f"❌ Error: {error}")