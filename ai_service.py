import os
from dotenv import load_dotenv
import instructor
import google.generativeai as genai
from models import AIProposal

# Load environment variables from .env file
load_dotenv()

def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it before running.")
    
    genai.configure(api_key=api_key)
    return instructor.from_gemini(
        client=genai.GenerativeModel("gemini-3.6-flash"),
        mode=instructor.Mode.GEMINI_JSON,
    )

async def generate_proposal(record_dict: dict) -> AIProposal:
    client = get_client()
    prompt = f"""
    You are an expert financial reconciliation AI auditing transactions.
    Analyze this settlement record and map it to ERP invoices.
    Record: {record_dict}
    
    CRITICAL INSTRUCTIONS:
    1. Extract the invoice IDs from the 'description' field.
    2. Look for explicit invoice totals mentioned in the description (e.g. "Total: 500.0"). This is the GROSS invoice amount.
    3. Calculate the EXPECTED NET AMOUNT for the invoice: Gross - (Gross * 0.02).
    4. Your allocated amount MUST exactly equal this EXPECTED NET AMOUNT.
    5. CLASSIFY THE TRANSACTION (`anomaly_flag`):
       - "BATCHED_SETTLEMENT": If multiple invoices are mentioned.
       - "MISSING_FEE": If the gateway_fee in the payload is exactly 0.0 or missing, but you expected a fee.
       - "AMOUNT_MISMATCH": If the payload's `amount` does NOT equal the sum of your EXPECTED NET AMOUNTS.
       - "CLEAN": If it perfectly matches one invoice with the correct 2% fee applied.
    6. Provide clear, step-by-step reasoning.
    """
    
    try:
        proposal = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=AIProposal,
        )
        return proposal
    except Exception as e:
        print(f"API Error Caught: {repr(e)}")
        # FALLBACK MECHANISM: Advanced Deterministic Regex Extractor
        import re
        from models import InvoiceMatch
        
        desc = record_dict.get("description", "")
        found_invs = re.findall(r"(INV-\d+)", desc)
        found_totals = re.findall(r"Total:\s*([\d\.]+)", desc)
        
        amount = float(record_dict.get("amount", 0.0))
        fee = float(record_dict.get("gateway_fee", 0.0))
        
        anomaly_flag = "CLEAN"
        expected_total_net = 0.0
        
        matches = []
        if found_invs:
            if len(found_invs) > 1:
                anomaly_flag = "BATCHED_SETTLEMENT"
                
            if found_totals:
                # Sum all explicitly stated totals (e.g. Total: 400, Total: 600 -> 1000)
                gross_total = sum(float(t) for t in found_totals)
                expected_fee = round(gross_total * 0.02, 2)
                total_net = gross_total - expected_fee
                expected_total_net = total_net
                # Distribute the net evenly for the proposal
                split_amount = total_net / len(found_invs)
            else:
                expected_fee = round(amount * 0.02, 2)
                total_net = amount - expected_fee
                expected_total_net = total_net
                split_amount = total_net / len(found_invs)
                
            matches = [InvoiceMatch(invoice_id=inv, allocated_amount=split_amount) for inv in found_invs]
            
        if fee == 0.0:
            anomaly_flag = "MISSING_FEE"
        elif abs(amount - (expected_total_net + expected_fee)) > 0.05 and anomaly_flag != "BATCHED_SETTLEMENT":
            anomaly_flag = "AMOUNT_MISMATCH"
            
        # Give a better fallback reasoning for the UI
        reasoning = f"FALLBACK: Expected Net: {expected_total_net}. Actual Payload: {amount} with fee {fee}."
        
        return AIProposal(
            settlement_id=record_dict.get("settlement_id", "FALLBACK"),
            anomaly_flag=anomaly_flag,
            confidence_score=0.5,
            proposed_matches=matches,
            reasoning=reasoning
        )
