import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from models import SettlementRecord
from gatekeeper import RulesEngine
from ai_service import generate_proposal
import audit_ledger
import uvicorn

import hmac
import hashlib
import json

from config import settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await audit_ledger.init_db()
    yield

app = FastAPI(title="Razorpay AI Finance Controller Webhook", lifespan=lifespan)
rules_engine = RulesEngine()

def verify_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Verifies the webhook signature using HMAC SHA256 (Standard Razorpay Security)"""
    expected_signature = hmac.new(
        key=secret.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

async def process_single_record(record: SettlementRecord):
    try:
        # 1. AI Proposes
        proposal = await generate_proposal(record.model_dump())
        
        # 2. Gatekeeper Validates
        evaluation = await rules_engine.evaluate(proposal, record)
        
        # 3. Final Write
        if evaluation["status"] == "REJECTED":
            metrics_counter["anomalies_rejected"] += 1
            await audit_ledger.log_transaction(
                settlement_id=record.settlement_id,
                status=evaluation["status"],
                failure_reason=evaluation.get("failure_type", "UNKNOWN"),
                details=evaluation.get("detail", ""),
                proposal_dict=proposal.model_dump() if hasattr(proposal, "model_dump") else {}
            )
            print(f"⚠️ REJECTED: {record.settlement_id} sent to audit ledger. Reason: {evaluation['failure_type']}")
        else:
            metrics_counter["successful_reconciliations"] += 1
            print(f"✅ SUCCESS: {record.settlement_id} written to master ledger.")
            
    except Exception as e:
        metrics_counter["system_errors"] += 1
        print(f"CRITICAL ERROR processing {record.settlement_id}: {str(e)}")
        await audit_ledger.log_transaction(
            settlement_id=record.settlement_id,
            status="ERROR",
            failure_reason="SYSTEM_ERROR",
            details=str(e),
            proposal_dict={}
        )

metrics_counter = {
    "total_webhooks_received": 0,
    "successful_reconciliations": 0,
    "anomalies_rejected": 0,
    "system_errors": 0
}

@app.get("/metrics")
async def get_metrics():
    """FinOps Observability endpoint for prometheus/dashboards."""
    return metrics_counter

@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Live Webhook Endpoint for Razorpay to POST settlement reports.
    """
    metrics_counter["total_webhooks_received"] += 1
    # 1. Security Check: Verify Razorpay Signature
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Razorpay-Signature header")
        
    raw_body = await request.body()
    if not verify_signature(raw_body, signature, settings.razorpay_webhook_secret):
        print("🚨 SECURITY ALERT: Invalid Webhook Signature Detected!")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload after security check passes
    payload = await request.json()

    # 2. Extract Idempotency Key (Mandatory for financial webhooks)
    idempotency_key = request.headers.get("x-idempotency-key", "")
    if not idempotency_key:
        idempotency_key = payload.get("idempotency_key", f"IDEMP_{payload.get('settlement_id')}")
        
    record = SettlementRecord(
        settlement_id=payload.get("settlement_id"),
        amount=payload.get("amount"),
        gateway_fee=payload.get("gateway_fee"),
        description=payload.get("description"),
        idempotency_key=idempotency_key
    )
    
    # 3. Enqueue the background task
    background_tasks.add_task(process_single_record, record)
    
    # 4. Immediately acknowledge receipt to Razorpay (200 OK)
    return {"status": "success", "message": "Webhook received, verified, and queued."}

if __name__ == "__main__":
    print("🚀 Starting Razorpay AI Controller Production Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
