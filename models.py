from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, date
from enum import Enum

class AnomalyType(str, Enum):
    CLEAN = "CLEAN"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_FEE = "MISSING_FEE"
    BATCHED_SETTLEMENT = "BATCHED_SETTLEMENT"
    UNKNOWN = "UNKNOWN"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"

class InvoiceMatch(BaseModel):
    invoice_id: str = Field(..., min_length=1, description="The exact ERP invoice ID")
    extracted_gross_amount: Decimal = Field(
        ..., ge=0, description="Gross total for this invoice as literally stated in the "
        "webhook description text. A reading-comprehension extraction, not a "
        "calculation — this is the ONLY per-invoice figure the Gatekeeper trusts."
    )
    allocated_amount: Decimal = Field(
        ..., ge=0, description="AI's advisory guess at the net allocation. Non-authoritative: "
        "shown in the audit trail / merchant UI for explainability only, never used "
        "by the Gatekeeper to decide pass/reject."
    )

class AIProposal(BaseModel):
    settlement_id: str
    anomaly_flag: AnomalyType = Field(description="Classification of the transaction")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    proposed_matches: List[InvoiceMatch]
    reasoning: str

class SettlementRecord(BaseModel):
    settlement_id: str
    amount: Decimal = Field(..., ge=0)
    gateway_fee: Decimal = Field(..., ge=0)
    description: str
    idempotency_key: str = Field(default="")
    merchant_id: str = Field(default="default_merchant")
    transit_status: Optional[str] = Field(default=None, description="INITIATED | IN_TRANSIT | SETTLED | REFUND_PENDING | REFUND_COMPLETE")
    expected_settle_date: Optional[str] = Field(default=None, description="ISO date when settlement is expected")

# ---------------------------------------------------------------------------
# Transit & Cash-Flow Models
# ---------------------------------------------------------------------------

class TransitTransaction(BaseModel):
    """Tracks a single fund movement through T+0 → T+7 lifecycle."""
    settlement_id: str
    invoice_id: str
    amount: Decimal
    transit_status: str = Field(description="INITIATED | IN_TRANSIT | SETTLED | REFUND_PENDING | REFUND_COMPLETE")
    initiated_date: str
    expected_settle_date: str
    actual_settle_date: Optional[str] = None
    days_in_transit: int = 0
    is_delayed: bool = False

class CashFlowSnapshot(BaseModel):
    """Aggregated view of funds across lifecycle stages."""
    merchant_id: str
    snapshot_time: str
    total_settled: Decimal = Decimal("0")
    total_in_transit: Decimal = Decimal("0")
    total_refund_pending: Decimal = Decimal("0")
    total_late_credits: Decimal = Decimal("0")
    transit_by_day: dict = Field(default_factory=dict, description="Breakdown: {'T+1': amount, 'T+2': amount, ...}")
    delayed_items: List[TransitTransaction] = Field(default_factory=list)
    projected_inflow_7d: Decimal = Decimal("0")

# ---------------------------------------------------------------------------
# Compliance Shield Models
# ---------------------------------------------------------------------------

class ComplianceProofReport(BaseModel):
    """Tamper-evident Proof of Business document for compliance review."""
    report_id: str
    merchant_id: str
    generated_at: str
    period_start: str
    period_end: str
    total_transactions: int
    total_passed: int
    total_rejected: int
    total_settled_amount: Decimal
    rejection_rate: float
    risk_level: str = Field(description="GREEN | AMBER | RED")
    matched_records: List[dict] = Field(default_factory=list, description="Each settlement paired with its matched invoices")
    verification_hash: str = Field(description="SHA-256 of the deterministic data for tamper evidence")

# ---------------------------------------------------------------------------
# Resolution Assistant Models
# ---------------------------------------------------------------------------

class ResolutionStep(BaseModel):
    """A single actionable resolution step for the customer."""
    step_number: int
    action: str
    detail: str
    is_automated: bool = False
    cta_label: Optional[str] = None