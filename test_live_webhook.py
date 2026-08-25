import requests
import json
import hmac
import hashlib

# Configuration
WEBHOOK_URL = "http://localhost:8000/webhook/razorpay"
SECRET = "buildathon_secret_2026"

def send_test_webhook():
    payload = {
        "settlement_id": "SETT_SECURE_001",
        "amount": 5000.0,
        "gateway_fee": 100.0,
        "description": "Settlement for INV-999 (Total: 5000)",
        "idempotency_key": "IDEMP_SECURE_01"
    }
    
    # Convert payload to bytes for HMAC signing
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    
    # Calculate HMAC SHA256 Signature
    signature = hmac.new(
        key=SECRET.encode('utf-8'),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature,
        "x-idempotency-key": payload["idempotency_key"]
    }
    
    print("🚀 Sending Secure Webhook to FastAPI Server...")
    print(f"Payload: {payload}")
    print(f"Signature: {signature}")
    
    # We must send the exact bytes we signed
    response = requests.post(WEBHOOK_URL, data=payload_bytes, headers=headers)
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {response.text}")

if __name__ == "__main__":
    send_test_webhook()
