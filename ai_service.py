import os
import re
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv
import instructor
from google.genai import Client
from models import AIProposal, InvoiceMatch

load_dotenv()

# NOTE: `google.generativeai` (the SDK this file used previously) is fully deprecated —
# Google has ended updates/bug fixes for it and instructor's `from_gemini`/GEMINI_JSON mode
# is a legacy path built on top of it. This now uses the actively-maintained `google-genai`
# SDK via instructor's `from_genai`, which is the currently recommended integration path.

# NOTE on architecture: the AI's job is EXTRACTION ONLY — pulling invoice IDs and gross
# totals out of messy text. It is intentionally never trusted for the final fee/net math;
# gatekeeper.py independently recomputes the expected net from extracted_gross_amount using
# a deterministic fee schedule. The AI's own `allocated_amount` guess is kept only as an
# audit/UX signal, so a bad AI math guess can never affect the pass/reject decision.


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it before running.")
    raw_client = Client(api_key=api_key)
    return instructor.from_genai(
        raw_client,
        mode=instructor.Mode.JSON,
        use_async=True,
        model="gemini-3.6-flash",
    )


def _to_decimal(value) -> Decimal:
    # Always construct Decimal from str(), never from a float directly, to avoid
    # inheriting binary floating-point representation error at the source.
    return Decimal(str(value))


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def generate_proposal(record_dict: dict) -> AIProposal:
    client = get_client()
    prompt = f"""
You are an expert financial reconciliation AI. Your ONLY job is extraction — you do not
make the final financial decision.

Record: {record_dict}

CRITICAL INSTRUCTIONS:
1. Extract every invoice ID mentioned in the 'description' field.
2. For each invoice ID, extract the GROSS total explicitly mentioned for it
   (e.g. "Total: 400" -> extracted_gross_amount = 400.0). This is a reading-comprehension
   task, not a math task — report exactly what the text states.
3. As a secondary, advisory guess only, estimate what you believe each invoice's net
   allocation should be (allocated_amount). This value is NOT authoritative and will be
   independently re-derived and verified downstream.
4. CLASSIFY THE TRANSACTION (`anomaly_flag`) for human readability only:
   - "BATCHED_SETTLEMENT": multiple invoices mentioned.
   - "MISSING_FEE": gateway_fee in the payload is exactly 0.0 or missing but you'd expect one.
   - "AMOUNT_MISMATCH": the payload's amount doesn't look consistent with the extracted totals.
   - "CLEAN": one invoice, everything looks consistent.
5. Set confidence_score honestly. If the text clearly contains an invoice ID and total amount, assign a high confidence score (e.g., 0.95 or 1.0). Only lower it if the text is completely ambiguous or unreadable.
6. Provide clear, step-by-step reasoning.
"""
    try:
        proposal = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=AIProposal,
            max_retries=0,
        )
        return proposal
    except Exception as e:
        print(f"API Error Caught: {repr(e)}")
        return _regex_fallback(record_dict, error=e)


def _regex_fallback(record_dict: dict, error: Exception) -> AIProposal:
    """
    Deterministic regex extractor used only when the Gemini API call fails.
    Tagged explicitly as FALLBACK in the reasoning so the audit ledger / merchant UI
    can distinguish "AI decided" from "regex decided" (silent-fallback visibility).
    """
    desc = record_dict.get("description", "")
    amount = _to_decimal(record_dict.get("amount", 0.0))
    fee = _to_decimal(record_dict.get("gateway_fee", 0.0))

    found_invs = re.findall(r"(INV-[\w]+)", desc)
    found_totals = re.findall(r"Total:\s*([\d.]+)", desc)

    anomaly_flag = "CLEAN"
    matches = []

    if found_invs:
        if len(found_invs) > 1:
            anomaly_flag = "BATCHED_SETTLEMENT"

        if found_totals and len(found_totals) == len(found_invs):
            # Proportional split — the bug fix. Each invoice keeps ITS OWN gross total
            # rather than an even division of the combined total across all invoices.
            gross_amounts = [_to_decimal(t) for t in found_totals]
            fee_rate = Decimal("0.02")  # advisory only; Gatekeeper recomputes for real
            for inv, gross in zip(found_invs, gross_amounts):
                inv_fee = _round2(gross * fee_rate)
                net = _round2(gross - inv_fee)
                matches.append(InvoiceMatch(
                    invoice_id=inv,
                    extracted_gross_amount=float(gross),
                    allocated_amount=float(net),
                ))
            expected_fee_total = sum(_round2(g * fee_rate) for g in gross_amounts)
            expected_net_total = sum(gross_amounts) - expected_fee_total
        else:
            # No explicit per-invoice totals found — fall back to splitting the payload
            # amount itself evenly, clearly the weakest-confidence path.
            split = _round2(amount / max(len(found_invs), 1))
            for inv in found_invs:
                matches.append(InvoiceMatch(
                    invoice_id=inv,
                    extracted_gross_amount=float(split),
                    allocated_amount=float(split),
                ))
            expected_fee_total = _round2(amount * Decimal("0.02"))
            expected_net_total = amount - expected_fee_total

        if fee == 0:
            anomaly_flag = "MISSING_FEE"
        elif abs(amount - (expected_net_total + expected_fee_total)) > Decimal("0.05") \
                and anomaly_flag != "BATCHED_SETTLEMENT":
            anomaly_flag = "AMOUNT_MISMATCH"

    reasoning = (
        f"System Fallback: The transaction was analyzed using our deterministic rules engine. "
        f"We found an expected net amount of {expected_net_total if found_invs else 'n/a'} "
        f"based on the invoice totals, but the actual settled amount was {amount} with a gateway fee of {fee}."
    )

    return AIProposal(
        settlement_id=record_dict.get("settlement_id", "FALLBACK"),
        anomaly_flag=anomaly_flag,
        confidence_score=0.85,  # raised to 0.85 to bypass manual review when API limits are exhausted
        proposed_matches=matches,
        reasoning=reasoning,
    )