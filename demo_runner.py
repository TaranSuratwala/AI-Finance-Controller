import requests
import json
import hmac
import hashlib
import time
import os
import sys
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://localhost:8000/webhook/razorpay")
SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "buildathon_secret_2026")

def sign_payload(payload_dict: dict, secret: str = SECRET) -> str:
    payload_bytes = json.dumps(payload_dict, separators=(',', ':')).encode('utf-8')
    return hmac.new(
        key=secret.encode('utf-8'),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest(), payload_bytes

def send_webhook(payload: dict, custom_sig: str = None, idempotency_key: str = None):
    sig, payload_bytes = sign_payload(payload)
    if custom_sig:
        sig = custom_sig

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "x-idempotency-key": idempotency_key or payload.get("idempotency_key", "")
    }

    try:
        response = requests.post(WEBHOOK_URL, data=payload_bytes, headers=headers)
        return response.status_code, response.text
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to FastAPI server at http://localhost:8000")
        print("👉 Please make sure the server is running with: python main.py\n")
        return 0, "Connection Refused"

def run_case_a():
    print("\n" + "="*70)
    print("🔹 CASE A: Clean Multi-Invoice Settlement (Straight-Through Processing)")
    print("="*70)
    payload = {
        "settlement_id": f"SETT_CLEAN_{int(time.time())}",
        "amount": 1000.0,
        "gateway_fee": 20.0,
        "description": "Settlement for INV-100 (Total: 400.0), INV-101 (Total: 600.0)",
        "idempotency_key": f"IDEMP_CLEAN_{int(time.time())}"
    }
    print(f"Payload: {json.dumps(payload, indent=2)}")
    status, body = send_webhook(payload)
    print(f"\n📡 Response Status: {status}")
    print(f"📄 Response Body: {body}")
    print("👉 Check FastAPI terminal: Should show [✅ SUCCESS: ... written to master ledger]")

def run_case_b():
    print("\n" + "="*70)
    print("🔹 CASE B: Amount Mismatch Anomaly (51 Paise Discrepancy)")
    print("="*70)
    payload = {
        "settlement_id": f"SETT_MISMATCH_{int(time.time())}",
        "amount": 980.51,
        "gateway_fee": 0.0,
        "description": "INV-102 (Total: 980.0)",
        "idempotency_key": f"IDEMP_AMT_{int(time.time())}"
    }
    print(f"Payload: {json.dumps(payload, indent=2)}")
    status, body = send_webhook(payload)
    print(f"\n📡 Response Status: {status}")
    print(f"📄 Response Body: {body}")
    print("👉 Check FastAPI terminal: Should show [⚠️ REJECTED: ... Reason: AMOUNT_MISMATCH]")
    print("👉 Check Streamlit Merchant Support Portal: Generates 'Request Payment Link for Balance' button!")

def run_case_c():
    print("\n" + "="*70)
    print("🔹 CASE C: Stale ERP State (Closed Invoice INV-999)")
    print("="*70)
    payload = {
        "settlement_id": f"SETT_STALE_{int(time.time())}",
        "amount": 5000.0,
        "gateway_fee": 100.0,
        "description": "Settlement for INV-999 (Total: 5000)",
        "idempotency_key": f"IDEMP_STALE_{int(time.time())}"
    }
    print(f"Payload: {json.dumps(payload, indent=2)}")
    status, body = send_webhook(payload)
    print(f"\n📡 Response Status: {status}")
    print(f"📄 Response Body: {body}")
    print("👉 Check FastAPI terminal: Should show [⚠️ REJECTED: ... Reason: STALE_STATE]")
    print("👉 Check Streamlit Merchant Support Portal: Generates 'Reopen Invoice & Reprocess' button!")

def run_case_d():
    print("\n" + "="*70)
    print("🔹 CASE D: Duplicate Webhook / Replay Attack (Redis Idempotency)")
    print("="*70)
    fixed_idemp = f"IDEMP_DUP_TEST_{int(time.time())}"
    payload = {
        "settlement_id": f"SETT_DUP_{int(time.time())}",
        "amount": 400.0,
        "gateway_fee": 8.0,
        "description": "Settlement for INV-100 (Total: 400.0)",
        "idempotency_key": fixed_idemp
    }
    print("1️⃣ Sending original webhook first time...")
    status1, body1 = send_webhook(payload, idempotency_key=fixed_idemp)
    print(f"Status 1: {status1} | Body: {body1}")
    time.sleep(2)
    
    print("\n2️⃣ Sending duplicate webhook second time with SAME idempotency key...")
    payload["settlement_id"] = f"SETT_DUP_REPLAY_{int(time.time())}"
    status2, body2 = send_webhook(payload, idempotency_key=fixed_idemp)
    print(f"Status 2: {status2} | Body: {body2}")
    print("👉 Check FastAPI terminal: Gatekeeper catches DUPLICATE_WEBHOOK via Redis lock!")

def run_case_e():
    print("\n" + "="*70)
    print("🔹 CASE E: Security Alert — Tampered HMAC Signature")
    print("="*70)
    payload = {
        "settlement_id": "SETT_HACKER_999",
        "amount": 99999.0,
        "gateway_fee": 0.0,
        "description": "Illegitimate settlement",
        "idempotency_key": "IDEMP_HACK_01"
    }
    tampered_sig = "a1b2c3d4e5f60718293a4b5c6d7e8f90deadbeef"
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"Forged Signature: {tampered_sig}")
    status, body = send_webhook(payload, custom_sig=tampered_sig)
    print(f"\n📡 Response Status: {status} (Expected: 401 Unauthorized)")
    print(f"📄 Response Body: {body}")
    print("👉 Cryptographic verification blocked request at the gateway boundary!")

def run_all_interactive():
    print("\n🛡️  RAZORPAY BUILDATHON 2026 — LIVE DEMO RUNNER")
    print("="*70)
    print("1. Run All Cases in Sequence (Recommended for Video Recording)")
    print("2. Run Case A: Clean Multi-Invoice (Passes)")
    print("3. Run Case B: Amount Mismatch 51 Paise (Gatekeeper Rejection)")
    print("4. Run Case C: Stale ERP Closed Invoice (Gatekeeper Rejection)")
    print("5. Run Case D: Duplicate Webhook (Redis Idempotency Block)")
    print("6. Run Case E: Tampered Signature (Security 401)")
    print("q. Exit")
    print("="*70)
    
    choice = input("\nSelect an option [1-6, q]: ").strip()
    if choice == "1":
        run_case_e()
        time.sleep(2)
        run_case_a()
        time.sleep(3)
        run_case_b()
        time.sleep(3)
        run_case_c()
        time.sleep(3)
        run_case_d()
    elif choice == "2":
        run_case_a()
    elif choice == "3":
        run_case_b()
    elif choice == "4":
        run_case_c()
    elif choice == "5":
        run_case_d()
    elif choice == "6":
        run_case_e()
    else:
        print("Exiting.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_case_e()
        time.sleep(1)
        run_case_a()
        time.sleep(2)
        run_case_b()
        time.sleep(2)
        run_case_c()
        time.sleep(2)
        run_case_d()
    else:
        run_all_interactive()
