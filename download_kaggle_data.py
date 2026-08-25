import json
import random
import os
import kagglehub
import pandas as pd

def main():
    print("Downloading PaySim Dataset from Kaggle...")
    # This automatically downloads the dataset to a local cache and returns the path
    dataset_path = kagglehub.dataset_download('ealaxi/paysim1')
    
    csv_file = None
    for file in os.listdir(dataset_path):
        if file.endswith('.csv'):
            csv_file = os.path.join(dataset_path, file)
            break
            
    if not csv_file:
        print("No CSV found in the downloaded dataset.")
        return

    print(f"Loading data from {csv_file}...")
    # Read a random sample of 50 rows from the dataset
    # The dataset is huge, so we sample to keep the script fast
    df = pd.read_csv(csv_file, skiprows=lambda i: i > 0 and random.random() > 0.001)
    df = df.sample(n=min(50, len(df)))
    
    dataset = []
    
    # Let's map PaySim columns (amount, nameOrig, nameDest) into our SettlementRecord schema
    print("Transforming transactions into adversarial test cases...")
    
    for idx, row in df.iterrows():
        base_amt = float(row['amount'])
        fee = round(base_amt * 0.02, 2) # Simulate a 2% gateway fee
        
        # We will inject some chaos based on the original data
        chaos_type = random.choice(["CLEAN", "AMOUNT_MISMATCH", "STALE_STATE", "MISSING_FEE"])
        
        expected_status = "PASSED"
        expected_failure_type = None
        description = f"Settlement from {row['nameOrig']} to {row['nameDest']} (Ref: {row['step']})"
        
        # Inject Chaos
        if chaos_type == "AMOUNT_MISMATCH":
            base_amt += 0.51 # Trigger the >50 paise mismatch
            expected_status = "REJECTED"
            expected_failure_type = "AMOUNT_MISMATCH"
            
        elif chaos_type == "STALE_STATE":
            # Append '99' to the ID in description so Gatekeeper thinks it's closed
            description = f"Settlement for Invoice {row['nameDest']}99"
            expected_status = "REJECTED"
            expected_failure_type = "STALE_STATE"
            
        elif chaos_type == "MISSING_FEE":
            fee = 0.0
            expected_status = "REJECTED"
            expected_failure_type = "AMOUNT_MISMATCH" # AI will expect fee but it's missing, throwing off the calc

        dataset.append({
            "test_case_id": f"KAGGLE_{row['nameOrig']}_{idx}",
            "expected_status": expected_status,
            "expected_failure_type": expected_failure_type,
            "record": {
                "settlement_id": f"TXN_{row['nameOrig']}",
                "amount": round(base_amt, 2),
                "gateway_fee": round(fee, 2),
                "description": description
            }
        })

    with open("kaggle_dataset.json", "w") as f:
        json.dump(dataset, f, indent=4)
        
    print(f"✅ Generated kaggle_dataset.json with {len(dataset)} real-world derived records.")
    print("You can now modify your eval_ui.py to load 'kaggle_dataset.json' instead of 'synthetic_dataset.json'")

if __name__ == "__main__":
    main()
