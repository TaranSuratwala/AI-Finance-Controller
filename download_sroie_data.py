import json
import random
import requests

# SROIE (ICDAR 2019 "Scanned Receipts OCR and Information Extraction") is a real, public
# dataset of 626+ genuinely scanned retail receipts with human-annotated ground truth for
# company name, date, address, and total. This is the strongest "real-world" claim we can
# honestly make: real company names and real totals from real receipts.
#
# What IS real: company names, totals, the messiness of real-world date formats.
# What is NOT real: the settlement/webhook wrapper text and the injected chaos labels
# (AMOUNT_MISMATCH, STALE_STATE, etc.) — those are synthesized on top, same as
# download_github_data.py, because no public dataset of real Razorpay settlement
# webhooks exists (it's private financial data).

REPO_API = "https://api.github.com/repos/zzzDavid/ICDAR-2019-SROIE/contents/data/key"
RAW_BASE = "https://raw.githubusercontent.com/zzzDavid/ICDAR-2019-SROIE/master/data/key/"


def main():
    print("Fetching real scanned-receipt annotations (SROIE, ICDAR 2019) from GitHub...")
    resp = requests.get(REPO_API, headers={"Accept": "application/vnd.github+json"})
    if resp.status_code != 200:
        print(f"Failed to list dataset files (HTTP {resp.status_code}). Aborting.")
        return

    files = [f["name"] for f in resp.json() if f["name"].endswith(".json")]
    if not files:
        print("No annotation files found. Aborting.")
        return

    sample_files = random.sample(files, min(50, len(files)))
    dataset = []

    print(f"Downloading {len(sample_files)} real receipt annotations and injecting adversarial chaos...")
    for idx, fname in enumerate(sample_files):
        r = requests.get(RAW_BASE + fname)
        if r.status_code != 200:
            continue
        try:
            receipt = r.json()
            base_amt = float(str(receipt.get("total", "0")).replace(",", "").strip())
        except (ValueError, json.JSONDecodeError):
            continue
        if base_amt <= 0:
            continue

        company = (receipt.get("company") or "Unknown Vendor").strip()[:35]
        fee = round(base_amt * 0.02, 2)  # simulated 2% gateway fee

        chaos_type = random.choice(
            ["CLEAN", "AMOUNT_MISMATCH", "STALE_STATE", "MISSING_FEE", "BATCHED_SETTLEMENT", "DUPLICATE_WEBHOOK"]
        )
        expected_status = "PASSED"
        expected_failure_type = None
        idempotency_key = f"IDEMP_SROIE_{idx}"
        inv_num = 5000 + idx  # avoid colliding with other datasets' invoice ID ranges

        description = f"Settlement from {company} — Invoice INV-{inv_num} (Total: {base_amt})"

        if chaos_type == "AMOUNT_MISMATCH":
            base_amt += 0.51
            expected_status = "REJECTED"
            expected_failure_type = "AMOUNT_MISMATCH"

        elif chaos_type == "STALE_STATE":
            description = f"Settlement from {company} — Invoice INV-{inv_num}99 (Total: {base_amt})"
            expected_status = "REJECTED"
            expected_failure_type = "STALE_STATE"

        elif chaos_type == "MISSING_FEE":
            fee = 0.0
            expected_status = "REJECTED"
            expected_failure_type = "AMOUNT_MISMATCH"

        elif chaos_type == "BATCHED_SETTLEMENT":
            half = round(base_amt / 2, 2)
            other_half = round(base_amt - half, 2)
            description = (
                f"Batched settlement from {company}. "
                f"INV-{inv_num}_A (Total: {half}) and INV-{inv_num}_B (Total: {other_half})"
            )
            expected_status = "PASSED"

        elif chaos_type == "DUPLICATE_WEBHOOK":
            idempotency_key = f"DUP_SROIE_{idx}"
            expected_status = "REJECTED"
            expected_failure_type = "DUPLICATE_WEBHOOK"

        dataset.append({
            "test_case_id": f"SROIE_{idx}",
            "expected_status": expected_status,
            "expected_failure_type": expected_failure_type,
            "record": {
                "settlement_id": f"TXN_SROIE_{idx}",
                "amount": round(base_amt, 2),
                "gateway_fee": round(fee, 2),
                "description": description,
                "idempotency_key": idempotency_key,
            },
        })

    with open("sroie_dataset.json", "w") as f:
        json.dump(dataset, f, indent=4)

    print(f"Success! Generated sroie_dataset.json with {len(dataset)} test cases built from REAL "
          f"scanned-receipt company names and totals (ICDAR 2019 SROIE dataset).")


if __name__ == "__main__":
    main()
