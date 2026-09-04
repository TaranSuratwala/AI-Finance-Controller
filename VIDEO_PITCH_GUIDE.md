# 🎬 Razorpay Buildathon 2026: Official Video Production & Pitch Guide
**Project:** AI Finance Controller — Verifiable Autonomous Reconciliation  
**Target Video Duration:** 2:45 to 3:00 Minutes  
**Tone:** Confident, Technical, Visionary, Fintech-Rigorous  

---

## 📋 Executive Overview for the Video

Hackathon judges at Razorpay evaluate projects based on:
1. **Fintech Domain Relevance:** Does it solve a real, high-dollar pain point for Razorpay merchants and payment gateways?
2. **Technical Depth & Innovation:** Is it more than just a naive LLM wrapper? (Our answer: Dual-layer AI Auditor + Deterministic Gatekeeper, cryptographic HMAC signatures, Redis atomic idempotency, resilient regex fallback).
3. **Financial Safety / Zero-Hallucination:** How does it protect ledgers against mathematical hallucinations and false positives?
4. **User Experience (Merchant & FinOps):** Does it empower non-technical users to self-resolve exceptions instead of filing support tickets?
5. **Hard Proof / Empirical Metrics:** Did you validate it with benchmarks? (100% STP, 0% False Positive Rate across 3 datasets).

---

## 🛠️ Recording Setup & Assets Prepared for You

You have ready-made tools in this repository to record the video with zero stress:

| Asset | File Path | What to use it for |
|---|---|---|
| **Interactive Presentation Deck** | [`presentation.html`](presentation.html) | Open in Chrome/Edge (`start presentation.html`). Use Arrow keys to present Slides 1–6 with built-in teleprompter (press `N`). |
| **Live Demo Webhook Runner** | [`demo_runner.py`](demo_runner.py) | Run `python demo_runner.py` to trigger live signed webhooks during the screen recording. |
| **Production Webhook Server** | [`main.py`](main.py) | Run `python main.py` (FastAPI with HMAC SHA-256 security on port 8000). |
| **FinOps & Merchant UI** | [`eval_ui.py`](eval_ui.py) | Run `python -m streamlit run eval_ui.py` (Port 8501) for the Evaluation Matrix & Merchant Resolution Portal. |
| **Postman Collection** | [`Razorpay_Live_Demo.postman_collection.json`](Razorpay_Live_Demo.postman_collection.json) | Ready-to-import Postman collection with automatic HMAC signing script. |

---

## ⏱️ Video Storyboard & Shot-by-Shot Script (0:00 – 3:00)

```
[0:00 - 0:25] The Hook: The Billion-Dollar B2B Problem
[0:25 - 0:55] The Dilemma: Why Naive LLMs Cause Ledger Catastrophe
[0:55 - 1:25] The Innovation: Dual-Layer AI Auditor + Deterministic Gatekeeper
[1:25 - 2:15] Live Demo: Webhooks, HMAC, Rejections & Idempotency
[2:15 - 2:40] UX Delight: Merchant Self-Service & FinOps Audit Ledger
[2:40 - 3:00] Hard Proof & The Razorpay-Ready Close
```

---

### ACT 1: The Hook (0:00 – 0:25)

* **Visual on Screen:**
  - Option A (Camera): You on camera, speaking directly with professional confidence.
  - Option B (Slides): Show [`presentation.html`](presentation.html) **Slide 1 (Title & Hero)** in fullscreen.
* **Audio / Voiceover (Word-for-Word):**
  > "Every single day, payment gateways like Razorpay process millions of B2B transactions. But behind the scenes, finance teams are drowning in manual reconciliation.
  > 
  > Why? Because B2B payments are messy. A merchant receives a batched settlement, but the description is an unstructured string like: *'Settlement for invoice 100 and invoice 101 minus fees.'*
  > 
  > Standard regex breaks. Traditional AI hallucinates the math.
  > 
  > For the Razorpay Buildathon 2026, I built the **AI Finance Controller**—a zero-hallucination reconciliation engine that solves this permanently."

---

### ACT 2: The Dilemma: Why Naive LLMs Break (0:25 – 0:55)

* **Visual on Screen:**
  - Switch to [`presentation.html`](presentation.html) **Slide 2 (The Fintech Dilemma)**.
  - Highlight the two contrasting cards: *Unstructured Payment Memos* vs *The Hallucination Trap*.
* **Audio / Voiceover (Word-for-Word):**
  > "The fundamental problem with using generative AI in fintech is the **False Positive Risk**.
  > 
  > Large language models are probabilistic. If you ask an LLM to calculate a 2% gateway fee across split invoices, it can hallucinate—marking an invoice as settled when it was actually short by 50 paise.
  > 
  > In fintech, a False Positive is catastrophic: it causes silent, permanent financial leakage.
  > 
  > Our design principle was simple: **Never allow an LLM to calculate the final financial truth.**"

---

### ACT 3: The Breakthrough Architecture (0:55 – 1:25)

* **Visual on Screen:**
  - Switch to [`presentation.html`](presentation.html) **Slide 3 (System Architecture)**.
  - Mouse hover sequentially across Gate 0, Layer 1 (AI Auditor), Layer 2 (Deterministic Gate), and the Output Ledgers.
* **Audio / Voiceover (Word-for-Word):**
  > "To solve this, we designed a dual-layer architecture that separates reading comprehension from mathematical truth.
  > 
  > **Layer 1 is our AI Auditor**, powered by Google Gemini 3.6 Flash. Its ONLY job is entity extraction: reading unstructured memos and extracting invoice IDs and gross totals into strict Pydantic schemas. It is strictly forbidden from final math.
  > 
  > **Layer 2 is our Deterministic Gatekeeper**—a Python rules engine. It takes the AI's extracted figures, independently recalculates the exact gateway fee schedule, verifies down-to-the-paise tolerances, locks the invoice in Redis, and checks ERP state.
  > 
  > If the numbers don't match down to the decimal, the transaction is safely blocked."

---

### ACT 4: Live Technical Demonstration (1:25 – 2:15)

* **Visual on Screen:**
  - Split screen or window switch:
    - **Left Window:** Terminal running `python main.py` (FastAPI logs) or `eval_ui.py` Streamlit dashboard.
    - **Right Window:** Postman or running `python demo_runner.py`.
* **Action 1 (Security & Webhook Ingestion):**
  - Show Postman sending a signed POST to `/webhook/razorpay`.
  - Point to header `X-Razorpay-Signature` (HMAC SHA-256).
  - *Voiceover:* 
    > "Let's see it live. A Razorpay settlement webhook arrives. First, our server cryptographically verifies the HMAC SHA-256 signature. If a hacker tampers with the payload, it is rejected with a 401 Unauthorized before any AI processing."
* **Action 2 (Clean Multi-Invoice Processing):**
  - Send Case A in Postman or `python demo_runner.py` (Option 2).
  - Show the FastAPI terminal log: `✅ SUCCESS: ... written to master ledger`.
  - *Voiceover:*
    > "Next, here is a batched settlement for multiple invoices. The AI extracts both invoice IDs, the Gatekeeper validates the math, and the transaction is written straight to the master ledger in milliseconds."
* **Action 3 (Adversarial Math Discrepancy & Stale State):**
  - Send Case B (51 paise mismatch) or Case C (`INV-999` closed invoice).
  - Show terminal log: `⚠️ REJECTED: SETT_... sent to audit ledger. Reason: AMOUNT_MISMATCH`.
  - *Voiceover:*
    > "Now watch an adversarial case. The payload is short by just 51 paise. Traditional LLMs might gloss over this, but our Gatekeeper catches the discrepancy immediately. The transaction is rejected and routed to our forensic audit ledger."
* **Action 4 (Redis Idempotency Replay Protection):**
  - Send the exact same webhook again.
  - Show duplicate blocked.
  - *Voiceover:*
    > "And if that exact webhook is resent? Our Redis atomic lock catches the duplicate idempotency key instantly. No double-crediting, ever."

---

### ACT 5: FinOps & Merchant Support Portal (2:15 – 2:40)

* **Visual on Screen:**
  - Switch to browser tab: **Streamlit UI** (`http://localhost:8501`).
  - Click on **Tab 3: "🛍️ Merchant & End-User View"**.
  - Expand the transaction card and click the blue button: **"Request Payment Link for Balance"** or **"Reopen Invoice & Reprocess"**.
  - Watch the green success banner appear!
* **Audio / Voiceover (Word-for-Word):**
  > "Instead of dumping cryptic error codes into a log file, we built a merchant self-service experience.
  > 
  > In our Merchant Support Portal, the AI translates technical gatekeeper rejections into plain English: *'Invoice 102 was short by 51 paise after fees.'*
  > 
  > With one click, the merchant can generate a Razorpay payment link for the missing balance or reopen a closed ERP invoice. The system doesn't just catch errors—it automates their resolution."

---

### ACT 6: Hard Proof & The Close (2:40 – 3:00)

* **Visual on Screen:**
  - Switch to **Tab 1: "Detailed Evaluation Matrix"** in Streamlit showing the metrics bar:
    - Overall System Accuracy: **100%**
    - False Positive Rate: **0.0%**
    - Straight-Through Processing: **100%**
    - Anomalies Blocked: **100%**
  - Or switch to [`presentation.html`](presentation.html) **Slide 6 (Proven Across 3 Stress Datasets)**.
* **Audio / Voiceover (Word-for-Word):**
  > "We rigorously stress-tested this system across three datasets: synthetic adversarial cases, real credit data, and real-world OCR receipts from the ICDAR SROIE benchmark.
  > 
  > The result? **100% system accuracy, 100% straight-through processing on clean data, and a 0% false positive rate.**
  > 
  > The AI Finance Controller is fully containerized with Docker, asynchronously resilient with fallback parsers, and ready to be integrated into Razorpay's infrastructure today.
  > 
  > Thank you, and I look forward to your questions!"

---

## 🖥️ Step-by-Step Recording Guide (How to Record Like a Pro)

### 1. Recommended Recording Software (All Free)
- **OBS Studio (Best Quality):** Set canvas to 1920x1080, 60fps. Add two scenes:
  1. *Scene 1: Browser* (capturing `presentation.html` and Streamlit).
  2. *Scene 2: Split View* (Browser + Terminal / Postman).
- **Loom or Screen Studio (Easiest / Fast):** Great for instant picture-in-picture with cursor zooming.
- **Clipchamp / CapCut (Free Editing):** Built into Windows 11. Super easy to trim cuts and add captions.

### 2. Pre-Recording Terminal Setup
Open 3 terminal tabs in VS Code before starting:

* **Terminal 1 (Backend Server):**
  ```bash
  python main.py
  ```
  *(Wait until you see: "Starting Razorpay AI Controller Production Server on port 8000...")*

* **Terminal 2 (Streamlit UI):**
  ```bash
  python -m streamlit run eval_ui.py
  ```
  *(Opens `http://localhost:8501` in your browser)*

* **Terminal 3 (Live Demo Trigger):**
  ```bash
  python demo_runner.py
  ```
  *(Keep ready to send Case A, B, C, D at the click of a button)*

* **Browser Tab 1:** Open `presentation.html` (Press `F11` for fullscreen).  
* **Browser Tab 2:** Streamlit Dashboard at `http://localhost:8501`.

### 3. Voiceover Options
- **Option 1 (Your Own Voice):** Use a clean headset mic or laptop mic with noise suppression enabled.
- **Option 2 (AI Voiceover):** If you prefer not to record your voice, paste the verbatim scripts above into **ElevenLabs** (free tier has great realistic voices like "Adam" or "Rachel") or **Clipchamp AI Text-to-Speech**, and overlay the audio onto your screen recording!

---

## 🎯 Submission Checklist for Razorpay Buildathon 2026

- [ ] Video duration is between **2:30 and 3:00 minutes**.
- [ ] Video resolution is **1080p (1920x1080)**.
- [ ] Video mentions **Razorpay Buildathon 2026** in the first 10 seconds.
- [ ] Shows the **FastAPI HMAC authentication** (`X-Razorpay-Signature`).
- [ ] Shows the **Gatekeeper math rejection** (preventing False Positives).
- [ ] Shows the **Streamlit FinOps & Merchant Support Portal** with interactive resolution buttons.
- [ ] Shows the **Evaluation Metrics** (100% STP, 0% FPR).
- [ ] Video link uploaded to **YouTube (Unlisted)** or **Loom / Google Drive** with public viewing access.
