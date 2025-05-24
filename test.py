# Test script - save as test_connection.py
from binance import Client

API_KEY = "f41efa9502b1d83fb973333e0b37a2d6211cc636effdfc687950715a7881d0a5"
SECRET =  "4a1524037685e523ede375c283b06f5d58702cf5afb1254f4889bed16d208c7a"

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
