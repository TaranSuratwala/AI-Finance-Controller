"""
Compliance Shield — Proactive Compliance for Account Freeze Mitigation
========================================================================
Extends the deterministic gatekeeper's perfectly reconciled ledger data into
automated "Proof of Business" reports.  When Razorpay's risk engine flags an
account, the Controller can instantly feed deterministic, verified transaction
histories to the compliance team, reducing freeze duration and preventing
regulatory escalations.

Addresses Rank #1 quantified market need (₹38 Cr modeled annual exposure from
account freezes / rolling reserves).
"""

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal

import audit_ledger
from models import ComplianceProofReport


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


async def build_proof_of_business(
    merchant_id: str,
    period_start: str,
    period_end: str,
) -> ComplianceProofReport:
    """
    Build a tamper-evident Proof of Business report.

    Queries audit_log for all PASSED + REJECTED records in the date range,
    pairs each settlement to its matched invoices (from ai_proposal JSON),
    and computes a SHA-256 verification hash over the deterministic data.
    """
    records = await audit_ledger.get_audit_records_for_period(
        merchant_id, period_start, period_end
    )

    passed = [r for r in records if r["status"] == "PASSED"]
    rejected = [r for r in records if r["status"] == "REJECTED"]
    total = len(records)

    # Build matched_records — each settlement paired with its invoices
    matched_records = []
    total_settled = Decimal("0")

    for rec in records:
        proposal_data = {}
        try:
            proposal_data = json.loads(rec.get("ai_proposal", "{}") or "{}")
        except (json.JSONDecodeError, TypeError):
            pass

        invoices = []
        for m in proposal_data.get("proposed_matches", []):
            invoices.append({
                "invoice_id": m.get("invoice_id", ""),
                "gross_amount": m.get("extracted_gross_amount", 0),
                "allocated_amount": m.get("allocated_amount", 0),
            })

        entry = {
            "settlement_id": rec["settlement_id"],
            "timestamp": rec["timestamp"],
            "status": rec["status"],
            "failure_reason": rec.get("failure_reason"),
            "matched_invoices": invoices,
        }
        matched_records.append(entry)

        if rec["status"] == "PASSED":
            for inv in invoices:
                total_settled += Decimal(str(inv.get("gross_amount", 0)))

    # Compute rejection rate
    rejection_rate = (len(rejected) / total * 100) if total > 0 else 0.0

    # Risk level assessment
    risk_level = assess_compliance_risk_level(rejection_rate, total, len(rejected))

    # SHA-256 verification hash over the deterministic data
    hash_payload = json.dumps(matched_records, sort_keys=True, cls=_DecimalEncoder)
    verification_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

    report = ComplianceProofReport(
        report_id=f"CPR-{uuid.uuid4().hex[:12].upper()}",
        merchant_id=merchant_id,
        generated_at=datetime.utcnow().isoformat(),
        period_start=period_start,
        period_end=period_end,
        total_transactions=total,
        total_passed=len(passed),
        total_rejected=len(rejected),
        total_settled_amount=total_settled,
        rejection_rate=round(rejection_rate, 2),
        risk_level=risk_level,
        matched_records=matched_records,
        verification_hash=verification_hash,
    )

    # Persist the report
    await audit_ledger.store_compliance_report(
        merchant_id=merchant_id,
        report_json=json.dumps(report.model_dump(), cls=_DecimalEncoder),
        period_start=period_start,
        period_end=period_end,
        verification_hash=verification_hash,
    )

    return report


def assess_compliance_risk_level(rejection_rate: float, total_txns: int, rejected_count: int) -> str:
    """
    Deterministic risk scoring.
      GREEN : rejection_rate < 5% and fewer than 3 rejections
      AMBER : rejection_rate 5–15% or 3–10 rejections
      RED   : rejection_rate > 15% or more than 10 rejections
    """
    if rejection_rate > 15 or rejected_count > 10:
        return "RED"
    if rejection_rate >= 5 or rejected_count >= 3:
        return "AMBER"
    return "GREEN"


def format_for_razorpay_review(report: ComplianceProofReport) -> dict:
    """Serialise the report into a format consumable by Razorpay's risk engine."""
    return {
        "document_type": "PROOF_OF_BUSINESS",
        "report_id": report.report_id,
        "merchant_id": report.merchant_id,
        "period": f"{report.period_start} → {report.period_end}",
        "summary": {
            "total_transactions": report.total_transactions,
            "passed": report.total_passed,
            "rejected": report.total_rejected,
            "settled_amount": float(report.total_settled_amount),
            "rejection_rate_pct": report.rejection_rate,
            "risk_level": report.risk_level,
        },
        "verification_hash": report.verification_hash,
        "generated_at": report.generated_at,
        "matched_records": report.matched_records,
    }
