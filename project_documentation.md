# 🛡️ AI Finance Controller - Complete Project Documentation
**Event:** Razorpay Buildathon 2026

---

## 1. The Problem: B2B Payment Chaos
In modern fintech, B2B payment reconciliation is notoriously difficult. When a business receives a batched settlement (e.g., via NEFT/RTGS or a payment gateway), the associated webhook or bank statement often contains unstructured, messy descriptions like:
> *"Settlement for INV-100 (Total: 400), and INV-101 (Total: 600) minus fees"*

**Why traditional systems fail:**
1. **Regex/Rules Engines:** Fail when the text format changes slightly, or when delimiters are messy (e.g., typos, extra slashes).
2. **Standard LLMs (Generative AI):** LLMs are terrible at deterministic mathematics. If you ask an LLM to calculate gateway fees and split amounts, it will hallucinate (e.g., marking an invoice as paid when the amount was actually 50 paise short). In finance, **False Positives are unacceptable**.

## 2. The Solution: AI Auditor + Deterministic Gatekeeper
We built a dual-layer architecture to eliminate LLM hallucinations while retaining the LLM's incredible text-parsing abilities.

*   **Layer 1: Independent AI Auditor (Gemini 3.6 Flash + Instructor):** We restrict the AI from doing final math. Its only job is to extract the gross invoice totals and IDs from the messy text into a strict JSON schema.
*   **Layer 2: The Deterministic Gatekeeper:** A Python rules-engine that takes the AI's extracted data, rigorously calculates the exact 2% gateway fee, and checks it against the actual webhook payload down to the decimal point. If there is a mismatch, the transaction is **Blocked**.

## 3. System Architecture & Tech Stack
The project is built as a production-grade microservice.

### Tech Stack:
*   **Backend:** FastAPI (Asynchronous web server)
*   **AI Engine:** Google Gemini 3.6 Flash via `instructor` (for strict Pydantic JSON outputs).
*   **Frontend/Dashboards:** Streamlit, Pandas, Altair (for analytics)
*   **Database:** SQLite (Immutable Audit Ledger)
*   **DevOps:** Docker & Docker Compose

### Architecture Flow:
1. **Webhook Ingestion:** Razorpay sends a POST request to `/webhook/razorpay`.
2. **Security & Idempotency (Gate 0):** FastAPI verifies the `X-Razorpay-Signature` (HMAC SHA256) and logs the `x-idempotency-key` to prevent duplicate processing. Returns `200 OK` instantly.
3. **Background Processing:** The payload enters a background task.
4. **AI Proposal:** The AI generates an `AIProposal` classifying the transaction.
5. **Gatekeeper Validation:** The Rules Engine verifies the math.
6. **Audit & UI:** Approved transactions go to the Master Ledger. Rejected ones go to the Immutable Audit Ledger, which instantly populates the Merchant Support Portal in Streamlit.

## 4. Key Achievements & Outcomes
*   🏆 **100% Accuracy on Adversarial Data:** Achieved 100% Overall System Accuracy across 3 massive datasets (Synthetic, GitHub Real Amounts, and SROIE ICDAR 2019 Real OCR Receipts).
*   🚀 **Straight-Through Processing (STP):** Achieved 100% STP for valid transactions, successfully reconciling them without human intervention.
*   🛡️ **Anomaly Detection:** Successfully blocked 100% of adversarial anomalies (Amount Mismatches, Missing Fees, Stale States, Duplicate Webhooks).
*   🚀 **Production Ready:** Built a true async API with cryptographic security, rather than just a hackathon script.
*   🛍️ **Merchant UX:** Transformed raw JSON errors into actionable UI buttons (e.g., "Request Payment Link for Balance") for end-users.

## 5. Failures Encountered & How We Solved Them

### Failure 1: LLM Math Hallucinations on Batched Invoices
*   **The Issue:** When splitting a ₹1,000 payment across two invoices, the LLM would occasionally mess up the 2% fee deduction, allocating incorrect nets.
*   **The Fix:** We completely rewrote the prompt and architecture. We stopped asking the AI to calculate the net amount. We built the "Independent Auditor" paradigm, offloading math to the Python Gatekeeper.

### Failure 2: API Quota Limits (HTTP 429) During Bulk Processing
*   **The Issue:** During the evaluation of 50+ records, the Gemini API hit rate limits, crashing the application and stalling the dashboard.
*   **The Fix:** We built a highly robust **Graceful Degradation Regex Fallback** in `ai_service.py`. If the API fails, it catches the exception and routes the text through a deterministic regex parser. The system never goes offline.

### Failure 3: Streamlit UI State Conflicts
*   **The Issue:** When adding interactive buttons to the Merchant Dashboard ("Reopen Invoice"), Streamlit threw `StreamlitValueAssignmentNotAllowedError` because of session state conflicts.
*   **The Fix:** We separated the widget ID keys from the boolean state-tracking keys, allowing smooth, real-time UI updates without reloading the database.

## 6. Future Improvements (Roadmap)
1. **Vector Database Integration (RAG):** If an invoice ID is misspelled in the webhook (e.g., `IVN-100` instead of `INV-100`), we could use vector embeddings to search an ERP database and find the closest matching open invoice.
2. **Razorpay Dynamic Fee Structures:** Abstracting the deterministic `RulesEngine` to dynamically support Razorpay's varying fee tiers based on payment methods (e.g., 2% for Domestic Cards, 3% for International Cards, 0% for UPI) instead of a static percentage.
3. **Automated Refund Generation:** Connecting the Gatekeeper directly to the Razorpay Refunds API to automatically reverse `AMOUNT_MISMATCH` settlements without human intervention.
