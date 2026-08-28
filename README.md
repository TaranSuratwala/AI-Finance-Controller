# AI Finance Controller

AI Finance Controller is a deterministic reconciliation system for payment-webhook workflows.  
It combines LLM-powered extraction with strict rule-based validation to prevent incorrect settlement posting.

## Why this project

B2B settlements often arrive as unstructured descriptions, while accounting systems require exact math and traceable decisions.  
This project is designed to:

- parse noisy payment descriptions into structured invoice data,
- validate fee and net-amount math deterministically,
- enforce idempotency and stale-state checks,
- provide an auditable rejection trail for finance operations.

## Core architecture

1. **Webhook ingestion (FastAPI)** receives Razorpay settlement payloads.
2. **AI proposal layer** extracts invoice references and totals from free text.
3. **Deterministic gatekeeper** recalculates expected amounts and validates policy rules.
4. **Audit ledger + support UI** records rejected events and exposes operator-friendly explanations.

## Key capabilities

- HMAC signature validation for `X-Razorpay-Signature`
- Background processing with immediate API acknowledgment
- Duplicate webhook protection via idempotency handling
- Deterministic rejection reasons for audit and support workflows
- Streamlit dashboard for evaluation and merchant-support visibility

## Technology stack

- **Backend:** Python, FastAPI, AsyncIO
- **AI extraction:** Gemini (schema-constrained via `instructor`)
- **Data and analysis:** SQLite, Pandas, Altair, Streamlit
- **Containerization:** Docker, Docker Compose

## Quick start

### 1) Configure environment

Create your environment file from the example:

```bash
cp .env.example .env
```

Set:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2) Run with Docker (recommended)

```bash
docker-compose up --build
```

- API: `http://localhost:8000`
- Streamlit UI: `http://localhost:8501`

### 3) Run locally (without Docker)

```bash
pip install -r requirements.txt
python main.py
```

In a second terminal:

```bash
python -m streamlit run eval_ui.py
```

## Developer workflow

Use this lightweight loop for day-to-day work:

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Run API service**: `python main.py`
3. **Run dashboard**: `python -m streamlit run eval_ui.py`
4. **Test webhook path**: `python test_live_webhook.py`
5. **Run evaluation script**: `python test_eval.py`

## Repository highlights

- `/main.py` — FastAPI webhook service entry point
- `/ai_service.py` — AI extraction and fallback logic
- `/gatekeeper.py` — deterministic validation engine
- `/audit_ledger.py` — rejection/audit persistence
- `/eval_ui.py` — evaluation and support dashboard

---

Built for reliable AI-assisted finance operations where false positives are not acceptable.
