"""
Transit Tracker — Cross-Period Visibility for Refunds & Settlements
====================================================================
Shifts focus from immediate batch math to Lifecycle Transaction Tracking.
Tags delayed refund reversals and late credits, computes T+N day buckets,
and provides a forward-looking settlement projection.

Addresses Rank #2 quantified market need (merchant churn from T+2–T+7
settlement/refund delays causing reconciliation variance).
"""

from datetime import datetime, timedelta
from decimal import Decimal

import audit_ledger
from models import TransitTransaction, CashFlowSnapshot


def classify_transit_status(initiated_date_str: str, settlement_days: int = 3) -> dict:
    """
    Map a transaction to its lifecycle stage based on T+N day calculation.

    Args:
        initiated_date_str: ISO date when the transaction was initiated.
        settlement_days: Expected settlement window (default T+3).

    Returns:
        dict with transit_status, expected_settle_date, days_in_transit, is_delayed.
    """
    today = datetime.utcnow().date()
    try:
        initiated = datetime.fromisoformat(initiated_date_str).date()
    except (ValueError, TypeError):
        initiated = today

    expected_settle = initiated + timedelta(days=settlement_days)
    days_in_transit = (today - initiated).days
    is_delayed = today > expected_settle

    if days_in_transit <= 0:
        status = "INITIATED"
    elif today <= expected_settle:
        status = "IN_TRANSIT"
    else:
        status = "IN_TRANSIT"  # still in transit but flagged delayed

    return {
        "transit_status": status,
        "expected_settle_date": expected_settle.isoformat(),
        "days_in_transit": max(0, days_in_transit),
        "is_delayed": is_delayed,
    }


def detect_delayed_refund(initiated_date_str: str, refund_window_days: int = 3) -> dict:
    """
    Identify refund reversals beyond the expected window and tag them.

    Returns:
        dict with is_delayed_refund, days_overdue, recommended_action.
    """
    today = datetime.utcnow().date()
    try:
        initiated = datetime.fromisoformat(initiated_date_str).date()
    except (ValueError, TypeError):
        initiated = today

    expected_refund = initiated + timedelta(days=refund_window_days)
    days_overdue = max(0, (today - expected_refund).days)
    is_delayed = days_overdue > 0

    if days_overdue > 7:
        action = "AUTO_ESCALATE"
    elif days_overdue > 3:
        action = "FLAG_FOR_REVIEW"
    else:
        action = "MONITOR"

    return {
        "is_delayed_refund": is_delayed,
        "days_overdue": days_overdue,
        "expected_refund_date": expected_refund.isoformat(),
        "recommended_action": action,
    }


async def record_transit_event(settlement_id: str, invoice_id: str, amount: float,
                                initiated_date: str, settlement_days: int = 3,
                                is_refund: bool = False,
                                merchant_id: str = "default_merchant"):
    """
    Classify and log a transit event into the transit ledger.
    """
    if is_refund:
        info = detect_delayed_refund(initiated_date)
        status = "REFUND_PENDING" if not info["is_delayed_refund"] else "REFUND_PENDING"
        expected = info["expected_refund_date"]
    else:
        info = classify_transit_status(initiated_date, settlement_days)
        status = info["transit_status"]
        expected = info["expected_settle_date"]

    await audit_ledger.log_transit_event(
        settlement_id=settlement_id,
        invoice_id=invoice_id,
        amount=amount,
        transit_status=status,
        expected_settle_date=expected,
        merchant_id=merchant_id,
    )
    return info


async def mark_settled(settlement_id: str, invoice_id: str, merchant_id: str = "default_merchant"):
    """Mark a transit item as SETTLED with the actual settlement date."""
    await audit_ledger.log_transit_event(
        settlement_id=settlement_id,
        invoice_id=invoice_id,
        amount=0,  # amount unchanged, just updating status
        transit_status="SETTLED",
        expected_settle_date="",
        actual_settle_date=datetime.utcnow().isoformat(),
        merchant_id=merchant_id,
    )


async def get_cashflow_snapshot(merchant_id: str = "default_merchant") -> CashFlowSnapshot:
    """
    Build a complete CashFlowSnapshot from the transit ledger.
    """
    summary = await audit_ledger.get_transit_summary(merchant_id)

    # Delayed items
    all_items = await audit_ledger.get_transit_items(merchant_id)
    today = datetime.utcnow().date()
    delayed = []
    for item in all_items:
        if item["transit_status"] in ("INITIATED", "IN_TRANSIT", "REFUND_PENDING"):
            try:
                expected = datetime.fromisoformat(item["expected_settle_date"]).date()
                if today > expected:
                    delayed.append(TransitTransaction(
                        settlement_id=item["settlement_id"],
                        invoice_id=item["invoice_id"],
                        amount=Decimal(str(item["amount"])),
                        transit_status=item["transit_status"],
                        initiated_date=item["timestamp"],
                        expected_settle_date=item["expected_settle_date"],
                        actual_settle_date=item.get("actual_settle_date"),
                        days_in_transit=(today - datetime.fromisoformat(item["timestamp"]).date()).days,
                        is_delayed=True,
                    ))
            except (ValueError, TypeError):
                pass

    # Forward projection: sum of in-transit items expected in next 7 days
    projected = Decimal("0")
    for item in all_items:
        if item["transit_status"] in ("INITIATED", "IN_TRANSIT"):
            try:
                expected = datetime.fromisoformat(item["expected_settle_date"]).date()
                if today <= expected <= today + timedelta(days=7):
                    projected += Decimal(str(item["amount"]))
            except (ValueError, TypeError):
                pass

    return CashFlowSnapshot(
        merchant_id=merchant_id,
        snapshot_time=datetime.utcnow().isoformat(),
        total_settled=Decimal(str(summary["settled"])),
        total_in_transit=Decimal(str(summary["in_transit"])),
        total_refund_pending=Decimal(str(summary["refund_pending"])),
        total_late_credits=Decimal(str(summary["late_credits"])),
        transit_by_day=summary["by_day"],
        delayed_items=delayed,
        projected_inflow_7d=projected,
    )
