"""Tests for Transit Tracker — Lifecycle classification & cash-flow snapshots."""
import asyncio
import os
import pytest
from datetime import datetime, timedelta

import audit_ledger
import transit_tracker

TEST_DB = "test_transit_ledger.db"


def setup_module():
    audit_ledger.DB_PATH = TEST_DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    asyncio.run(audit_ledger.init_db())


def teardown_module():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ---------------------------------------------------------------------------
# Unit tests for classify_transit_status
# ---------------------------------------------------------------------------

def test_classify_initiated_today():
    """A transaction initiated now should be INITIATED with 0 days in transit."""
    result = transit_tracker.classify_transit_status(datetime.utcnow().isoformat())
    assert result["transit_status"] == "INITIATED"
    assert result["days_in_transit"] == 0
    assert result["is_delayed"] is False


def test_classify_in_transit():
    """A transaction initiated 1 day ago with T+3 should be IN_TRANSIT."""
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
    result = transit_tracker.classify_transit_status(yesterday, settlement_days=3)
    assert result["transit_status"] == "IN_TRANSIT"
    assert result["days_in_transit"] == 1
    assert result["is_delayed"] is False


def test_classify_delayed():
    """A transaction initiated 5 days ago with T+3 should be delayed."""
    five_days_ago = (datetime.utcnow() - timedelta(days=5)).isoformat()
    result = transit_tracker.classify_transit_status(five_days_ago, settlement_days=3)
    assert result["is_delayed"] is True
    assert result["days_in_transit"] == 5


# ---------------------------------------------------------------------------
# Unit tests for detect_delayed_refund
# ---------------------------------------------------------------------------

def test_refund_not_delayed():
    """A refund initiated today should not be delayed."""
    result = transit_tracker.detect_delayed_refund(datetime.utcnow().isoformat())
    assert result["is_delayed_refund"] is False
    assert result["days_overdue"] == 0
    assert result["recommended_action"] == "MONITOR"


def test_refund_delayed_flag():
    """A refund initiated 5 days ago with T+3 window should be flagged."""
    five_days_ago = (datetime.utcnow() - timedelta(days=5)).isoformat()
    result = transit_tracker.detect_delayed_refund(five_days_ago, refund_window_days=3)
    assert result["is_delayed_refund"] is True
    assert result["days_overdue"] == 2
    assert result["recommended_action"] == "MONITOR"


def test_refund_auto_escalate():
    """A refund overdue by >7 days should auto-escalate."""
    long_ago = (datetime.utcnow() - timedelta(days=15)).isoformat()
    result = transit_tracker.detect_delayed_refund(long_ago, refund_window_days=3)
    assert result["is_delayed_refund"] is True
    assert result["days_overdue"] > 7
    assert result["recommended_action"] == "AUTO_ESCALATE"


# ---------------------------------------------------------------------------
# Integration tests for transit ledger
# ---------------------------------------------------------------------------

def test_record_and_snapshot():
    """Record transit events and verify the snapshot aggregation."""
    initiated = datetime.utcnow().isoformat()

    asyncio.run(transit_tracker.record_transit_event(
        settlement_id="SET-T1", invoice_id="INV-T1", amount=1000.0,
        initiated_date=initiated, merchant_id="test_merchant",
    ))
    asyncio.run(transit_tracker.record_transit_event(
        settlement_id="SET-T2", invoice_id="INV-T2", amount=500.0,
        initiated_date=initiated, is_refund=True, merchant_id="test_merchant",
    ))

    snapshot = asyncio.run(transit_tracker.get_cashflow_snapshot("test_merchant"))
    # At least the two items should be tracked
    assert float(snapshot.total_in_transit) + float(snapshot.total_refund_pending) > 0


def test_mark_settled():
    """Marking an item as settled should move it out of in-transit."""
    initiated = datetime.utcnow().isoformat()
    asyncio.run(transit_tracker.record_transit_event(
        settlement_id="SET-T3", invoice_id="INV-T3", amount=200.0,
        initiated_date=initiated, merchant_id="test_merchant",
    ))
    asyncio.run(transit_tracker.mark_settled("SET-T3", "INV-T3", "test_merchant"))

    items = asyncio.run(audit_ledger.get_transit_items("test_merchant", "SETTLED"))
    settled_ids = [i["settlement_id"] for i in items]
    assert "SET-T3" in settled_ids
