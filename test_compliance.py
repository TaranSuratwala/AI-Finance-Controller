"""Tests for Compliance Shield — Proof of Business & Risk Assessment."""
import asyncio
import os
import json
import pytest
import audit_ledger
import compliance_shield

TEST_DB = "test_audit_ledger.db"


def setup_module():
    audit_ledger.DB_PATH = TEST_DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    asyncio.run(audit_ledger.init_db())


def teardown_module():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def _seed_data():
    """Seed audit_log with a mix of PASSED and REJECTED records."""
    asyncio.run(audit_ledger.log_transaction(
        settlement_id="SET-001", status="PASSED", failure_reason="",
        details="OK", proposal_dict={
            "proposed_matches": [{"invoice_id": "INV-A", "extracted_gross_amount": 500.0, "allocated_amount": 490.0}]
        }, merchant_id="test_merchant",
    ))
    asyncio.run(audit_ledger.log_transaction(
        settlement_id="SET-002", status="REJECTED", failure_reason="AMOUNT_MISMATCH",
        details="Diff 200 paise", proposal_dict={
            "proposed_matches": [{"invoice_id": "INV-B", "extracted_gross_amount": 300.0, "allocated_amount": 294.0}]
        }, merchant_id="test_merchant",
    ))
    asyncio.run(audit_ledger.log_transaction(
        settlement_id="SET-003", status="PASSED", failure_reason="",
        details="OK", proposal_dict={
            "proposed_matches": [{"invoice_id": "INV-C", "extracted_gross_amount": 750.0, "allocated_amount": 735.0}]
        }, merchant_id="test_merchant",
    ))


def test_build_proof_of_business():
    _seed_data()
    report = asyncio.run(compliance_shield.build_proof_of_business(
        merchant_id="test_merchant",
        period_start="2000-01-01",
        period_end="2099-12-31",
    ))
    assert report.total_transactions == 3
    assert report.total_passed == 2
    assert report.total_rejected == 1
    assert report.total_settled_amount > 0
    assert len(report.verification_hash) == 64  # SHA-256 hex
    assert report.risk_level in ("GREEN", "AMBER", "RED")
    assert len(report.matched_records) == 3


def test_risk_level_green():
    level = compliance_shield.assess_compliance_risk_level(2.0, 100, 2)
    assert level == "GREEN"


def test_risk_level_amber():
    level = compliance_shield.assess_compliance_risk_level(8.0, 100, 8)
    assert level == "AMBER"


def test_risk_level_red():
    level = compliance_shield.assess_compliance_risk_level(20.0, 50, 11)
    assert level == "RED"


def test_format_for_razorpay_review():
    _seed_data()
    report = asyncio.run(compliance_shield.build_proof_of_business(
        merchant_id="test_merchant",
        period_start="2000-01-01",
        period_end="2099-12-31",
    ))
    formatted = compliance_shield.format_for_razorpay_review(report)
    assert formatted["document_type"] == "PROOF_OF_BUSINESS"
    assert "verification_hash" in formatted
    assert "summary" in formatted


def test_verification_hash_determinism():
    """Same data should produce the same hash."""
    _seed_data()
    r1 = asyncio.run(compliance_shield.build_proof_of_business(
        "test_merchant", "2000-01-01", "2099-12-31"
    ))
    r2 = asyncio.run(compliance_shield.build_proof_of_business(
        "test_merchant", "2000-01-01", "2099-12-31"
    ))
    assert r1.verification_hash == r2.verification_hash
