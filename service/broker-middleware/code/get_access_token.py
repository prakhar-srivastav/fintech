
from kiteconnect import KiteConnect
import logging
import os

# Enable debug logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

# Initialize Kite Connect
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

# Initialize Kite Connect
kite = KiteConnect(api_key=API_KEY)

# Step 2: Generate login URL
print("=" * 60)
print("KITE CONNECT AUTHENTICATION")
print("=" * 60)
print("\nStep 1: Copy this URL and open it in your browser:")
print(kite.login_url())
print("\nStep 2: Log in with your Zerodha credentials")
print("Step 3: After login, you'll be redirected to a URL")
print("Step 4: Copy the 'request_token' from the redirected URL")
print("\nThe URL will look like:")
print("http://127.0.0.1:5000/?request_token=XXXXXX&action=login&status=success")
print("-" * 60)

# Step 3: Get request token from user
request_token = input("\nPaste the request_token here: ").strip()

try:
    # Step 4: Generate access token
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    
    print("\n" + "=" * 60)
    print("SUCCESS! Authentication Complete")
    print("=" * 60)
    print(f"\nYour Access Token: {data['access_token']}")
    print(f"\nUser ID: {data['user_id']}")
    print(f"User Name: {data['user_name']}")
    print(f"Email: {data['email']}")
    
    # Set access token
    kite.set_access_token(data['access_token'])
    
    # Save to file for future use
    with open('kite_tokens.txt', 'w') as f:
        f.write(f"API_KEY = '{API_KEY}'\n")
        f.write(f"ACCESS_TOKEN = '{data['access_token']}'\n")
        f.write(f"USER_ID = '{data['user_id']}'\n")
    
    print("\n✓ Credentials saved to 'kite_tokens.txt'")
    print("\nNOTE: Access token is valid until 6:00 AM next day")
    print("You'll need to regenerate it daily")
    
    # Test the connection
    print("\n" + "-" * 60)
    print("Testing connection...")
    profile = kite.profile()
    print(f"✓ Connected successfully as: {profile['user_name']}")
    print("-" * 60)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    print("\nCommon issues:")
    print("1. Make sure API_KEY and API_SECRET are correct")
    print("2. Make sure you copied the complete request_token")
    print("3. Request token expires quickly - generate a new one if needed")