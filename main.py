import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Query
from models import SettlementRecord
from gatekeeper import RulesEngine
from ai_service import generate_proposal
import audit_ledger
import transit_tracker
import compliance_shield
import resolution_assistant
import uvicorn

import hmac
import hashlib
import json
from datetime import datetime, timedelta

from config import settings

from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await audit_ledger.init_db()
    yield

app = FastAPI(title="Razorpay AI Finance Controller Webhook", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
                proposal_dict=proposal.model_dump() if hasattr(proposal, "model_dump") else {},
                merchant_id=record.merchant_id,
            )
            print(f"⚠️ REJECTED: {record.settlement_id} sent to audit ledger. Reason: {evaluation['failure_type']}")
        else:
            metrics_counter["successful_reconciliations"] += 1
            # Log PASSED transactions too — required for Compliance Shield proof-of-business
            await audit_ledger.log_transaction(
                settlement_id=record.settlement_id,
                status="PASSED",
                failure_reason="",
                details="Reconciled successfully",
                proposal_dict=proposal.model_dump() if hasattr(proposal, "model_dump") else {},
                merchant_id=record.merchant_id,
            )
            print(f"✅ SUCCESS: {record.settlement_id} written to master ledger.")

        # 4. Log transit events for each matched invoice
        initiated_date = datetime.utcnow().isoformat()
        for match in proposal.proposed_matches:
            is_refund = "refund" in record.description.lower()
            await transit_tracker.record_transit_event(
                settlement_id=record.settlement_id,
                invoice_id=match.invoice_id,
                amount=float(match.extracted_gross_amount),
                initiated_date=initiated_date,
                is_refund=is_refund,
                merchant_id=record.merchant_id,
            )

        # 5. If passed, mark as settled
        if evaluation["status"] == "PASSED":
            for match in proposal.proposed_matches:
                await transit_tracker.mark_settled(
                    settlement_id=record.settlement_id,
                    invoice_id=match.invoice_id,
                    merchant_id=record.merchant_id,
                )
            
    except Exception as e:
        metrics_counter["system_errors"] += 1
        print(f"CRITICAL ERROR processing {record.settlement_id}: {str(e)}")
        await audit_ledger.log_transaction(
            settlement_id=record.settlement_id,
            status="ERROR",
            failure_reason="SYSTEM_ERROR",
            details=str(e),
            proposal_dict={},
            merchant_id=record.merchant_id,
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
@limiter.limit("5/minute")
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
        idempotency_key=idempotency_key,
        merchant_id=payload.get("merchant_id", "default_merchant"),
    )
    
    # 3. Enqueue the background task
    background_tasks.add_task(process_single_record, record)
    
    # 4. Immediately acknowledge receipt to Razorpay (200 OK)
    return {"status": "success", "message": "Webhook received, verified, and queued."}


# ---------------------------------------------------------------------------
# Compliance Shield Endpoints
# ---------------------------------------------------------------------------

@app.post("/compliance/proof-of-business")
async def generate_proof_of_business(
    merchant_id: str = Query(default="default_merchant"),
    period_start: str = Query(default=None),
    period_end: str = Query(default=None),
):
    """Generate a tamper-evident Proof of Business compliance report."""
    if not period_start:
        period_start = (datetime.utcnow() - timedelta(days=30)).isoformat()
    if not period_end:
        period_end = datetime.utcnow().isoformat()

    report = await compliance_shield.build_proof_of_business(
        merchant_id=merchant_id,
        period_start=period_start,
        period_end=period_end,
    )
    return report.model_dump()


@app.get("/compliance/risk-score")
async def get_risk_score(merchant_id: str = Query(default="default_merchant")):
    """Return current compliance risk assessment."""
    # Quick assessment from recent data
    period_start = (datetime.utcnow() - timedelta(days=30)).isoformat()
    period_end = datetime.utcnow().isoformat()
    records = await audit_ledger.get_audit_records_for_period(
        merchant_id, period_start, period_end
    )
    total = len(records)
    rejected = sum(1 for r in records if r["status"] == "REJECTED")
    rate = (rejected / total * 100) if total > 0 else 0.0
    risk_level = compliance_shield.assess_compliance_risk_level(rate, total, rejected)

    return {
        "merchant_id": merchant_id,
        "risk_level": risk_level,
        "rejection_rate": round(rate, 2),
        "total_transactions": total,
        "rejected_transactions": rejected,
        "period": f"{period_start} → {period_end}",
    }


# ---------------------------------------------------------------------------
# Cash Flow & Transit Tracker Endpoints
# ---------------------------------------------------------------------------

@app.get("/cashflow/snapshot")
async def cashflow_snapshot(merchant_id: str = Query(default="default_merchant")):
    """Return the transit-aware cash flow summary."""
    snapshot = await transit_tracker.get_cashflow_snapshot(merchant_id)
    return snapshot.model_dump()


@app.get("/cashflow/transit-items")
async def transit_items(
    merchant_id: str = Query(default="default_merchant"),
    status: str = Query(default=None),
):
    """Return individual in-transit items with T+N status."""
    items = await audit_ledger.get_transit_items(merchant_id, status)
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Resolution Assistant Endpoint
# ---------------------------------------------------------------------------

@app.get("/resolution/{failure_type}")
async def get_resolution_steps(
    failure_type: str,
    settlement_id: str = Query(default=""),
):
    """Return customer-facing resolution steps for a failure type."""
    steps = resolution_assistant.get_resolution(
        failure_type, {"settlement_id": settlement_id}
    )
    summary = resolution_assistant.generate_customer_summary(
        failure_type, settlement_id
    )
    return {
        "failure_type": failure_type,
        "steps": [s.model_dump() for s in steps],
        "customer_summary": summary,
    }


@app.post("/api/resolutions/{settlement_id}/request-payment-link")
async def request_payment_link(settlement_id: str):
    """Mocks creating a Razorpay Payment Link and resolves the issue."""
    # In reality, this would call razorpay.payment_link.create(...)
    await audit_ledger.resolve_rejection(settlement_id, "Payment Link Sent")
    return {"status": "success", "message": "Payment link dispatched.", "settlement_id": settlement_id}

@app.post("/api/resolutions/{settlement_id}/reopen-invoice")
async def reopen_invoice(settlement_id: str):
    """Mocks reopening the invoice via ERP webhook and resolves the issue."""
    # In reality, this would fire an ERP webhook to NetSuite/Zoho
    await audit_ledger.resolve_rejection(settlement_id, "Invoice Reopened")
    return {"status": "success", "message": "Invoice reopened in ERP.", "settlement_id": settlement_id}

@app.post("/api/resolutions/{settlement_id}/acknowledge")
async def acknowledge_issue(settlement_id: str):
    """Acknowledges duplicate or informational rejection."""
    await audit_ledger.resolve_rejection(settlement_id, "Acknowledged")
    return {"status": "success", "message": "Issue acknowledged.", "settlement_id": settlement_id}


if __name__ == "__main__":
    print("🚀 Starting Razorpay AI Controller Production Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
