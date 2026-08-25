import requests
import time

data = [
    {
        "settlement_id": "SETT_123",
        "amount": 105.00,
        "gateway_fee": 5.00,
        "description": "Razorpay payout for standard invoices"
    },
    {
        "settlement_id": "SETT_999",
        "amount": 50.00,
        "gateway_fee": 2.00,
        "description": "Test for stale state invoice 99"
    }
]

print("🚀 Sending batch to AI Finance Controller...")
response = requests.post("http://127.0.0.1:8000/v1/reconcile/batch", json=data)
print("Response:", response.json())

print("⏳ Waiting 5 seconds for background processing...")
time.sleep(5)

print("\n📊 Fetching Dashboard Results...")
dashboard = requests.get("http://127.0.0.1:8000/v1/dashboard")
import json
print(json.dumps(dashboard.json(), indent=2))
