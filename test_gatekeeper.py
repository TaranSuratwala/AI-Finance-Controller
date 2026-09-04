"""
Regression tests for the deterministic math gate.

Run with:  pytest test_gatekeeper.py -v
"""
import pytest
from decimal import Decimal

from gatekeeper import RulesEngine
from models import AIProposal, InvoiceMatch, SettlementRecord


def make_settlement(amount, gateway_fee, idempotency_key="IDEMP_TEST_1"):
    return SettlementRecord(
        settlement_id="stl_test",
        amount=Decimal(str(amount)),
        gateway_fee=Decimal(str(gateway_fee)),
        description="Total: 100",
        idempotency_key=idempotency_key,
    )


def make_proposal(gross, allocated):
    return AIProposal(
        settlement_id="stl_test",
        anomaly_flag="CLEAN",
        confidence_score=0.95,
        proposed_matches=[
            InvoiceMatch(invoice_id="INV-1", extracted_gross_amount=Decimal(str(gross)),
                         allocated_amount=Decimal(str(allocated)))
        ],
        reasoning="test",
    )


@pytest.mark.asyncio
async def test_passes_on_correct_extracted_gross_even_if_ai_math_is_wrong():
    """amount == sum(extracted_gross_amount); gateway_fee is informational only.
    The AI's allocated_amount (its own arithmetic) is hallucinated/wrong, but
    extracted_gross_amount (text extraction) is right — this MUST pass, proving
    the gate no longer relies on the AI's math."""
    engine = RulesEngine()
    settlement = make_settlement(amount=100, gateway_fee=2, idempotency_key="IDEMP_A")
    proposal = make_proposal(gross=100, allocated=9999)  # allocated_amount is nonsense
    result = await engine.evaluate(proposal, settlement)
    assert result["status"] == "PASSED"


@pytest.mark.asyncio
async def test_rejects_on_wrong_extracted_gross():
    """If the extraction itself is wrong, it must be caught — this is the figure
    the gate actually trusts."""
    engine = RulesEngine()
    settlement = make_settlement(amount=100, gateway_fee=2, idempotency_key="IDEMP_B")
    proposal = make_proposal(gross=150, allocated=100)  # extraction is wrong
    result = await engine.evaluate(proposal, settlement)
    assert result["status"] == "REJECTED"
    assert result["failure_type"] == "AMOUNT_MISMATCH"


@pytest.mark.asyncio
async def test_gateway_fee_does_not_affect_the_math_gate():
    """Same gross/amount pair, wildly different fee values — must still pass,
    since fee is not netted out of `amount` in this schema."""
    engine = RulesEngine()
    for fee, key, inv in [(0, "IDEMP_FEE0", "INV-A"), (5, "IDEMP_FEE5", "INV-B"), (20, "IDEMP_FEE20", "INV-C")]:
        settlement = SettlementRecord(
            settlement_id="stl_test", amount=Decimal("100"), gateway_fee=Decimal(str(fee)),
            description="Total: 100", idempotency_key=key,
        )
        proposal = AIProposal(
            settlement_id="stl_test", anomaly_flag="CLEAN", confidence_score=0.95, reasoning="test",
            proposed_matches=[InvoiceMatch(invoice_id=inv, extracted_gross_amount=Decimal("100"),
                                            allocated_amount=Decimal("100"))],
        )
        result = await engine.evaluate(proposal, settlement)
        if fee == 0:
            assert result["status"] == "REJECTED"
            assert result["failure_type"] == "MISSING_FEE"
        else:
            assert result["status"] == "PASSED", f"failed with fee={fee}: {result}"


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_is_caught_atomically():
    """Two webhooks sharing the same real idempotency key: only the first passes."""
    engine = RulesEngine()
    proposal = make_proposal(gross=100, allocated=98)
    s1 = make_settlement(amount=100, gateway_fee=2, idempotency_key="IDEMP_SHARED")
    s2 = make_settlement(amount=100, gateway_fee=2, idempotency_key="IDEMP_SHARED")

    first = await engine.evaluate(proposal, s1)
    second = await engine.evaluate(proposal, s2)

    assert first["status"] == "PASSED"
    assert second["status"] == "REJECTED"
    assert second["failure_type"] == "DUPLICATE_WEBHOOK"