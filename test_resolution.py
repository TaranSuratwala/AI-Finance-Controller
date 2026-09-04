"""Tests for AI Resolution Assistant — deterministic resolution step mapping."""
import pytest
import resolution_assistant
from models import ResolutionStep


# ---------------------------------------------------------------------------
# All known failure types should return non-empty resolution steps
# ---------------------------------------------------------------------------

FAILURE_TYPES = [
    "AMOUNT_MISMATCH",
    "MISSING_FEE",
    "STALE_STATE",
    "DUPLICATE_WEBHOOK",
    "ACCOUNT_FREEZE",
    "REFUND_DELAYED",
    "SYSTEM_ERROR",
]


@pytest.mark.parametrize("failure_type", FAILURE_TYPES)
def test_get_resolution_returns_steps(failure_type):
    steps = resolution_assistant.get_resolution(failure_type)
    assert len(steps) > 0
    assert all(isinstance(s, ResolutionStep) for s in steps)
    # Steps should be numbered sequentially
    assert [s.step_number for s in steps] == list(range(1, len(steps) + 1))


@pytest.mark.parametrize("failure_type", FAILURE_TYPES)
def test_generate_customer_summary_not_empty(failure_type):
    summary = resolution_assistant.generate_customer_summary(
        failure_type, "SET-999", "Test detail"
    )
    assert len(summary) > 50  # Should be a meaningful summary
    assert "SET-999" in summary
    assert "Recommended Steps" in summary


def test_unknown_failure_type_gets_fallback():
    """Unknown failure types should get a fallback resolution."""
    steps = resolution_assistant.get_resolution("TOTALLY_UNKNOWN_TYPE")
    assert len(steps) >= 1
    assert steps[0].action == "Review Transaction Details"


def test_context_injection():
    """Context dict should not break resolution generation."""
    steps = resolution_assistant.get_resolution(
        "AMOUNT_MISMATCH",
        {"settlement_id": "SET-CTX-001", "amount": 1500}
    )
    assert len(steps) > 0


def test_amount_mismatch_has_reconciliation_step():
    steps = resolution_assistant.get_resolution("AMOUNT_MISMATCH")
    actions = [s.action for s in steps]
    assert "Request Reconciliation" in actions


def test_account_freeze_has_proof_download():
    steps = resolution_assistant.get_resolution("ACCOUNT_FREEZE")
    actions = [s.action for s in steps]
    assert "Download Proof of Business Report" in actions


def test_duplicate_webhook_no_action_needed():
    steps = resolution_assistant.get_resolution("DUPLICATE_WEBHOOK")
    assert steps[0].action == "No Action Required"
    assert steps[0].is_automated is True


def test_refund_delayed_has_transit_tracker_step():
    steps = resolution_assistant.get_resolution("REFUND_DELAYED")
    actions = [s.action for s in steps]
    assert "Check Transit Tracker" in actions


def test_customer_summary_markdown_format():
    """Summary should be valid markdown with headers and numbered steps."""
    summary = resolution_assistant.generate_customer_summary(
        "MISSING_FEE", "SET-MD-001"
    )
    assert "###" in summary  # Has header
    assert "**1.**" in summary  # Has numbered steps
    assert "Transaction" in summary
