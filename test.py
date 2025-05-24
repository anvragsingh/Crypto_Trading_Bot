# Test script - save as test_connection.py
from binance import Client

API_KEY = "your_API_key_here"
SECRET =  "your_secret_key_here"

print("Testing API Connection...")
print(f"Using API Key: {API_KEY[:10]}...{API_KEY[-10:]}")

try:
    # Initialize client
    client = Client(API_KEY, SECRET, testnet=True)
    print("✅ Client initialized")
    
    # Test server time (no permissions needed)
    server_time = client.get_server_time()
    print(f"✅ Server connection OK: {server_time}")
    
    # Test account info (needs permissions)
    account = client.futures_account()
    print("✅ Account access successful!")
    
except Exception as e:
    print(f"❌ Error: {e}")
