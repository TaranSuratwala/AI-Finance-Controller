import json
import random
import pandas as pd
import requests
import io

def main():
    print("Downloading Credit Scoring Dataset from GitHub...")
    # A widely used public financial dataset hosted on GitHub
    url = "https://raw.githubusercontent.com/gastonstat/CreditScoring/master/CreditScoring.csv"
    response = requests.get(url)
    
    if response.status_code != 200:
        print("Failed to download dataset.")
        return

    print("Loading data...")
    # Read the CSV from the downloaded text
    df = pd.read_csv(io.StringIO(response.text))
    
    # Randomly sample 50 records for evaluation to keep it fast
    df = df.sample(n=min(50, len(df)))
    
    dataset = []
    
    print("Transforming transactions into adversarial test cases...")
    
    for idx, row in df.iterrows():
        base_amt = float(row['Amount'])
        fee = round(base_amt * 0.02, 2) # Simulate a 2% gateway fee
        
        # Inject Chaos
        chaos_type = random.choice(["CLEAN", "AMOUNT_MISMATCH", "STALE_STATE", "MISSING_FEE", "BATCHED_SETTLEMENT", "DUPLICATE_WEBHOOK"])
        
        expected_status = "PASSED"
        expected_failure_type = None
        idempotency_key = f"IDEMP_{idx}"
        
        # We synthesize a real-world looking description using the row's data
        job_type = ["Freelance", "Consulting", "Software", "Hardware", "Retail"][int(row['Job']) % 5]
        description = f"Settlement for {job_type} Invoice INV-{int(row['Price'])} (Total: {base_amt})"
        
        if chaos_type == "AMOUNT_MISMATCH":
            offset = max(0.51, base_amt * 0.01)
            base_amt += offset 
            expected_status = "REJECTED"
            expected_failure_type = "AMOUNT_MISMATCH"
            
        elif chaos_type == "STALE_STATE":
            description = f"Settlement for Invoice INV-{int(row['Price'])}99 (Total: {base_amt})"
            expected_status = "REJECTED"
            expected_failure_type = "STALE_STATE"
            
        elif chaos_type == "MISSING_FEE":
            fee = 0.0
            expected_status = "REJECTED"
            expected_failure_type = "MISSING_FEE"
            
        elif chaos_type == "BATCHED_SETTLEMENT":
            # Split the base amount into two invoices
            half = round(base_amt / 2, 2)
            other_half = base_amt - half
            description = f"Batched Settlement for {job_type}. INV-{int(row['Price'])}_A (Total: {half}) and INV-{int(row['Price'])}_B (Total: {other_half})"
            # It should pass normally!
            expected_status = "PASSED"
            
        elif chaos_type == "DUPLICATE_WEBHOOK":
            # We will use an idempotency key that starts with DUP_ to trigger Gatekeeper's duplicate logic for testing
            idempotency_key = f"DUP_{idx}"
            expected_status = "REJECTED"
            expected_failure_type = "DUPLICATE_WEBHOOK"

        dataset.append({
            "test_case_id": f"GITHUB_{idx}",
            "expected_status": expected_status,
            "expected_failure_type": expected_failure_type,
            "record": {
                "settlement_id": f"TXN_{idx}",
                "amount": round(base_amt, 2),
                "gateway_fee": round(fee, 2),
                "description": description,
                "idempotency_key": idempotency_key
            }
        })

    with open("github_dataset.json", "w") as f:
        json.dump(dataset, f, indent=4)
        
    print(f"Success! Generated github_dataset.json with {len(dataset)} real-world derived records.")

if __name__ == "__main__":
    main()
