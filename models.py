from pydantic import BaseModel, Field
from typing import List

class InvoiceMatch(BaseModel):
    invoice_id: str = Field(..., description="The exact ERP invoice ID")
    allocated_amount: float = Field(..., description="Amount allocated to this invoice")

class AIProposal(BaseModel):
    settlement_id: str
    anomaly_flag: str = Field(description="Classification of the transaction: CLEAN, AMOUNT_MISMATCH, MISSING_FEE, BATCHED_SETTLEMENT, or UNKNOWN")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    proposed_matches: List[InvoiceMatch]
    reasoning: str

class SettlementRecord(BaseModel):
    settlement_id: str
    amount: float
    gateway_fee: float
    description: str
    idempotency_key: str = Field(default="")
