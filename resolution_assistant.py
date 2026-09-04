"""
AI Resolution Assistant — Customer-Facing Resolution Steps
============================================================
Maps every failure type to deterministic, actionable resolution steps
in customer-friendly language.  No internal error codes are exposed;
each step includes a human-readable action, detail, and optional
automated CTA (call-to-action) button label.
"""

from typing import List
from models import ResolutionStep


# ---------------------------------------------------------------------------
# Resolution Step Definitions (deterministic — no LLM needed)
# ---------------------------------------------------------------------------

_RESOLUTION_MAP: dict[str, List[dict]] = {
    "AMOUNT_MISMATCH": [
        {
            "action": "Verify Invoice Totals",
            "detail": "Open your ERP/billing system and confirm the invoice totals match the settlement amount. "
                      "Look for partial payments, credit notes, or tax adjustments that may explain the difference.",
            "is_automated": False,
            "cta_label": None,
        },
        {
            "action": "Check for Partial Payments",
            "detail": "Some settlements are split across multiple batches. Check your Razorpay Dashboard → "
                      "Transactions → Filter by invoice ID to see if a second settlement is in transit.",
            "is_automated": False,
            "cta_label": "View in Dashboard",
        },
        {
            "action": "Request Reconciliation",
            "detail": "If the mismatch persists, submit a reconciliation request. The system has generated a "
                      "Proof of Business report with verified invoice↔settlement mappings that will be attached automatically.",
            "is_automated": True,
            "cta_label": "Request Reconciliation with Proof",
        },
    ],
    "MISSING_FEE": [
        {
            "action": "Review Fee Configuration",
            "detail": "Navigate to Razorpay Dashboard → Settings → Pricing to verify your current fee structure. "
                      "Check if a promotional fee waiver or custom pricing plan is active on your account.",
            "is_automated": False,
            "cta_label": "Open Fee Settings",
        },
        {
            "action": "Check Fee Waiver Status",
            "detail": "Some accounts have temporary fee waivers during onboarding or promotional periods. "
                      "If a waiver recently expired, the missing fee may be expected retroactive billing.",
            "is_automated": False,
            "cta_label": None,
        },
        {
            "action": "Flag for FinOps Review",
            "detail": "This transaction has been flagged for manual review by your finance team. "
                      "A notification with the settlement ID and audit trail has been sent.",
            "is_automated": True,
            "cta_label": "Send to FinOps Team",
        },
    ],
    "STALE_STATE": [
        {
            "action": "Reopen Invoice in ERP",
            "detail": "The invoice referenced in this settlement is marked as CLOSED in your ERP system, "
                      "but a new settlement has arrived for it. Reopen the invoice to allow reconciliation.",
            "is_automated": False,
            "cta_label": "Reopen Invoice",
        },
        {
            "action": "Trigger Re-Settlement",
            "detail": "Once the invoice is reopened, use the Razorpay API or Dashboard to trigger a "
                      "re-settlement. The system will automatically re-process in the next batch cycle.",
            "is_automated": True,
            "cta_label": "Re-process Settlement",
        },
        {
            "action": "Escalate if Persistent",
            "detail": "If the invoice cannot be reopened or the issue recurs, escalate to Razorpay support "
                      "with the audit trail attached. The system will include the full transaction history.",
            "is_automated": True,
            "cta_label": "Escalate with Audit Trail",
        },
    ],
    "DUPLICATE_WEBHOOK": [
        {
            "action": "No Action Required",
            "detail": "The system's idempotency guard detected this as a duplicate webhook delivery. "
                      "Your original transaction was already processed successfully. No double-booking occurred.",
            "is_automated": True,
            "cta_label": None,
        },
        {
            "action": "Verify Original Transaction",
            "detail": "For peace of mind, you can verify that the original transaction settled correctly "
                      "by checking your Razorpay Dashboard → Settlements → search by Settlement ID.",
            "is_automated": False,
            "cta_label": "View Original Transaction",
        },
    ],
    "ACCOUNT_FREEZE": [
        {
            "action": "Download Proof of Business Report",
            "detail": "The system has generated a tamper-evident Proof of Business report containing "
                      "all verified invoice↔settlement matches with a SHA-256 verification hash. "
                      "Download this report to submit to Razorpay's compliance team.",
            "is_automated": True,
            "cta_label": "Download Compliance Report",
        },
        {
            "action": "Submit to Razorpay Compliance",
            "detail": "Upload the Proof of Business report to Razorpay Dashboard → Compliance → "
                      "Submit Documentation. Include your Merchant ID for faster processing.",
            "is_automated": False,
            "cta_label": "Submit to Compliance",
        },
        {
            "action": "Request Freeze Review",
            "detail": "After submitting the report, request an expedited freeze review. The verification "
                      "hash ensures the data hasn't been tampered with, accelerating the review process.",
            "is_automated": True,
            "cta_label": "Request Expedited Review",
        },
    ],
    "REFUND_DELAYED": [
        {
            "action": "Check Transit Tracker",
            "detail": "Open the Cash Flow & Transit Tracker tab to see exactly where your refund is in the "
                      "T+2 to T+7 settlement pipeline. The tracker shows the expected settlement date.",
            "is_automated": False,
            "cta_label": "Open Transit Tracker",
        },
        {
            "action": "Monitor or Escalate",
            "detail": "If the refund is within the T+3 window, no action is needed — it will settle automatically. "
                      "If it is beyond T+7, the system will auto-escalate to Razorpay support.",
            "is_automated": True,
            "cta_label": None,
        },
        {
            "action": "Track Expected Settlement",
            "detail": "The system continuously monitors your pending refunds. You will receive a notification "
                      "when the refund settles or if it exceeds the expected window.",
            "is_automated": True,
            "cta_label": "View Expected Dates",
        },
    ],
    "SYSTEM_ERROR": [
        {
            "action": "Automatic Retry Scheduled",
            "detail": "The system encountered a temporary error processing this transaction. "
                      "An automatic retry has been scheduled. No action is needed from your side.",
            "is_automated": True,
            "cta_label": None,
        },
        {
            "action": "Contact Support if Persistent",
            "detail": "If this error appears repeatedly for the same transaction, contact Razorpay support "
                      "with the Settlement ID. The full error log has been preserved in the audit trail.",
            "is_automated": False,
            "cta_label": "Contact Support",
        },
    ],
}

# Fallback for unknown failure types
_DEFAULT_RESOLUTION = [
    {
        "action": "Review Transaction Details",
        "detail": "Check your Razorpay Dashboard for the latest status of this transaction. "
                  "The AI system has logged the full details in the audit trail for reference.",
        "is_automated": False,
        "cta_label": "View in Dashboard",
    },
    {
        "action": "Contact Support",
        "detail": "If the issue persists, contact Razorpay support with the Settlement ID "
                  "and the system will attach the relevant audit trail automatically.",
        "is_automated": False,
        "cta_label": "Contact Support",
    },
]


def get_resolution(failure_type: str, context: dict = None) -> List[ResolutionStep]:
    """
    Return actionable resolution steps for a given failure type.

    Args:
        failure_type: The gatekeeper failure classification.
        context: Optional dict with settlement_id, amount, etc. for personalization.

    Returns:
        Ordered list of ResolutionStep objects.
    """
    raw_steps = _RESOLUTION_MAP.get(failure_type, _DEFAULT_RESOLUTION)

    steps = []
    for i, step_data in enumerate(raw_steps, start=1):
        detail = step_data["detail"]
        # Inject context if available
        if context:
            sid = context.get("settlement_id", "")
            if sid and "{settlement_id}" in detail:
                detail = detail.replace("{settlement_id}", sid)

        steps.append(ResolutionStep(
            step_number=i,
            action=step_data["action"],
            detail=detail,
            is_automated=step_data.get("is_automated", False),
            cta_label=step_data.get("cta_label"),
        ))

    return steps


def generate_customer_summary(failure_type: str, settlement_id: str,
                               failure_detail: str = "") -> str:
    """
    Generate a human-readable markdown summary with resolution steps.

    Returns a customer-friendly string (no internal codes).
    """
    steps = get_resolution(failure_type, {"settlement_id": settlement_id})

    # Friendly titles
    _FRIENDLY_TITLES = {
        "AMOUNT_MISMATCH": "💰 Settlement Amount Discrepancy",
        "MISSING_FEE": "📋 Fee Configuration Issue",
        "STALE_STATE": "📄 Invoice Status Conflict",
        "DUPLICATE_WEBHOOK": "🔄 Duplicate Detection (No Action Needed)",
        "ACCOUNT_FREEZE": "🛡️ Account Compliance Review",
        "REFUND_DELAYED": "⏳ Refund Processing Update",
        "SYSTEM_ERROR": "⚙️ Temporary Processing Issue",
    }
    title = _FRIENDLY_TITLES.get(failure_type, "⚠️ Transaction Issue Detected")

    lines = [
        f"### {title}",
        f"**Transaction:** `{settlement_id}`",
        "",
    ]

    if failure_detail:
        lines.append(f"> {failure_detail}")
        lines.append("")

    lines.append("**Recommended Steps:**")
    lines.append("")

    for step in steps:
        auto_badge = " 🤖 *Automated*" if step.is_automated else ""
        lines.append(f"**{step.step_number}.** **{step.action}**{auto_badge}")
        lines.append(f"   {step.detail}")
        lines.append("")

    return "\n".join(lines)
