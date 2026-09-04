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

## 3. The Live Demo: The Architecture in Action (0:50 - 2:20)
*(Screen recording showing a live Postman/cURL request hitting the FastAPI endpoint alongside the backend logs or dashboard. Captions or voiceover narrate the flow).*

**You:** "Let's see this in action. A settlement webhook arrives. First, our asynchronous server instantly verifies the cryptographic **HMAC SHA256 Signature** to ensure enterprise security.

Next, the AI steps in. But here’s the architectural secret: the AI only *extracts* the unstructured data; it never calculates. 

*(Highlight Case A on screen)*
**Case A:** Watch this transaction. The AI's internal math hallucinated the wrong total, but its extraction of the invoice data was perfectly accurate. Because our Python Gatekeeper handles the deterministic math, the transaction still **passes**. We've neutralized the hallucination without failing the request.

*(Highlight Case B on screen)*
**Case B:** Now let's flip it. In this request, the AI extracts the wrong invoice amount. The Gatekeeper's strict mathematical check catches the discrepancy, and the transaction is safely **rejected**. 

*(Switch to the Merchant Support Portal tab).*
Instead of throwing a cryptic 500 error, rejected transactions hit our FinOps Audit Ledger. The AI translates the technical failure into a human-readable explanation, allowing the merchant to instantly trigger a payment link for the missing balance.

*(Send the same webhook again in Postman)*
Finally, if that exact same webhook hits our system again? Our Idempotency key extraction steps in. **Duplicate webhook rejected.**"

## 5. The Close (2:20 - 2:45)
*(Back to you on camera).*

**You:** "Security. Idempotency. Zero-hallucination mathematics. And a flawless Merchant UX. 
The AI Finance Controller doesn't just catch errors—it resolves them. It is fully Dockerized and ready to be deployed into Razorpay's infrastructure today.
Thank you for your time, and I look forward to your feedback."
