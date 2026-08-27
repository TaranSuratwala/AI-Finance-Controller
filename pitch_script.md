# 🛡️ AI Finance Controller: Video Pitch Script
**Target Length:** 2.5 - 3 Minutes
**Tone:** Professional, Confident, Technical yet Accessible

---

## 1. The Hook (0:00 - 0:20)
*(Upbeat, professional background music starts. You are on screen looking directly at the camera).*

**You:** "Every year, B2B payment gateways process billions of dollars. But behind the scenes, finance teams are drowning in manual reconciliation. Why? Because B2B payments are messy. A merchant receives a single ₹2,000 settlement, but the memo just says *'Payment for invoices 100, 101, and some other stuff.'* 
Standard parsers break. Traditional AI hallucinates the math.
For the Razorpay Buildathon 2026, I built the **AI Finance Controller**—a zero-hallucination reconciliation engine that solves this permanently."

## 2. The Problem & Solution (0:20 - 0:50)
*(Show a graphic of a messy webhook payload on screen vs. a clean ledger).*

**You:** "The problem with using standard LLMs for financial reconciliation is **False Positives**. If an AI hallucinates a math calculation, it might mark a partially unpaid invoice as fully settled. In fintech, a False Positive is unacceptable.
My solution pairs an **Independent Auditor AI** with a **Deterministic Gatekeeper**. The AI extracts the unstructured intent, but the Python-based Gatekeeper strictly enforces the mathematical reality. If they don't match down to the decimal, the transaction is safely blocked and logged."

## 3. The Demo: Frontend (0:50 - 1:40)
*(Screen recording of the Streamlit Dashboard. Show the Evaluation Matrix).*

**You:** "Let's look at the Evaluation Engine. We subjected our system to an adversarial dataset filled with missing fees, floating-point mismatches, batched settlements, and even prompt injections. 
As you can see, we achieved **100% accuracy** with a **0% False Positive Rate**.
But what happens when an anomaly is caught?"

*(Switch to the Merchant Support Portal tab).*

**You:** "Instead of throwing a cryptic 500 error, rejected transactions are sent to the FinOps Audit Ledger, and directly to the **Merchant Support Portal**. Our AI translates the technical failure—like an Amount Mismatch—into a human-readable explanation, allowing the merchant to instantly click a button to send a payment link for the remaining balance."

## 4. The Demo: Backend Architecture (1:40 - 2:20)
*(Show VS Code or a Terminal side-by-side with a Postman/cURL request).*

**You:** "But this isn't just a dashboard; it's a production-ready system. 
The backend is an asynchronous **FastAPI server** that exposes a live webhook endpoint. When Razorpay posts a settlement, we instantly verify the cryptographic **HMAC SHA256 Signature** to ensure enterprise security. We extract the Idempotency Key to prevent double-processing, acknowledge the webhook instantly, and process the AI reconciliation in the background. 
If the API rate limits hit? The system gracefully degrades to a deterministic Regex fallback engine, ensuring zero downtime."

## 5. The Close (2:20 - 2:45)
*(Back to you on camera).*

**You:** "Security. Idempotency. Zero-hallucination mathematics. And a flawless Merchant UX. 
The AI Finance Controller doesn't just catch errors—it resolves them. It is fully Dockerized and ready to be deployed into Razorpay's infrastructure today.
Thank you for your time, and I look forward to your feedback."
