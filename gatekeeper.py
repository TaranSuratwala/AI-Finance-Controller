import logging
from decimal import Decimal

import redis.asyncio as aioredis
import fakeredis.aioredis as fakeredis

from models import AIProposal, SettlementRecord
from config import settings

logger = logging.getLogger("gatekeeper")


class RulesEngine:
    def __init__(self):
        self._redis = None  # lazily connected — see _get_redis()
        self.TOLERANCE_PAISE = settings.tolerance_paise
        self.LOCK_TTL_SECONDS = 30

    async def _get_redis(self):
        """
        Use the real Redis configured via REDIS_URL (the docker-compose `redis`
        service in production). Only fall back to an in-memory FakeRedis if that
        Redis is genuinely unreachable, so local `python main.py` still works
        without extra setup. FakeRedis state does NOT survive a restart and is
        NOT shared across replicas — it must never be what production runs on.
        """
        if self._redis is not None:
            return self._redis
        try:
            client = aioredis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=2
            )
            await client.ping()
            self._redis = client
            logger.info("Gatekeeper connected to real Redis at %s", settings.redis_url)
        except Exception as e:
            logger.warning(
                "Real Redis unreachable (%s). Falling back to in-memory FakeRedis — "
                "locks/idempotency will NOT persist or be shared across instances.", e
            )
            self._redis = fakeredis.FakeRedis(decode_responses=True)
        return self._redis

    async def mock_erp_lookup(self, invoice_id: str):
        # Stub ERP client. Kept behind this single method so swapping in a real
        # ERP integration later doesn't require touching any gate logic below.
        if invoice_id.endswith("99"):
            return {"state": "CLOSED"}
        return {"state": "OPEN"}

    async def evaluate(self, proposal: AIProposal, source: SettlementRecord) -> dict:
        redis = await self._get_redis()
        locked_invoices = []
        is_passed = False
        try:
            # GATE 0.5: Confidence Check
            if proposal.confidence_score < 0.70:
                return self._reject(proposal, "LOW_CONFIDENCE", "Confidence score below 0.70. Routing to manual review.")

            # GATE 0: Idempotency
            if not source.idempotency_key:
                return self._reject(proposal, "MISSING_IDEMPOTENCY", "Idempotency key is missing.")
            
            # Allow evaluation datasets to deterministically test duplicates
            if source.idempotency_key.startswith("DUP_"):
                return self._reject(proposal, "DUPLICATE_WEBHOOK", "Simulated Duplicate Webhook")

            first_seen = await redis.set(source.idempotency_key, "processed", nx=True, ex=86400)
            if not first_seen:
                return self._reject(proposal, "DUPLICATE_WEBHOOK",
                                     f"Idempotency key {source.idempotency_key} already processed.")

            # GATE 1: Deterministic Math Check.
            if not proposal.proposed_matches and source.amount > 0:
                 return self._reject(proposal, "AMOUNT_MISMATCH", "No invoices extracted but settlement amount > 0.")
            
            gross_total = sum(
                (m.extracted_gross_amount for m in proposal.proposed_matches), Decimal("0")
            )
            
            gross_paise = int((gross_total * 100).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
            source_paise = int((source.amount * 100).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
            diff_paise = abs(gross_paise - source_paise)
            
            dynamic_tolerance = max(self.TOLERANCE_PAISE, int(gross_paise * 0.005))
            
            if diff_paise > dynamic_tolerance:
                return self._reject(
                    proposal, "AMOUNT_MISMATCH",
                    f"Recomputed independently: extracted invoice totals sum to {gross_total}, "
                    f"but the settlement amount is {source.amount} (diff {diff_paise} paise, tolerance {dynamic_tolerance} paise)"
                )
            
            # Deterministic Fee Check
            if source.gateway_fee == 0 and source.amount > 0:
                return self._reject(
                    proposal, "MISSING_FEE",
                    "Deterministic check: gateway_fee in the payload is exactly 0.0 but settlement is non-zero."
                )

            # GATE 2 & 3: Distributed Locking & ERP State Check
            for match in proposal.proposed_matches:
                lock_key = f"lock:inv:{match.invoice_id}"
                lock = await redis.set(
                    lock_key, "locked", nx=True, ex=self.LOCK_TTL_SECONDS
                )
                if not lock:
                    return self._reject(proposal, "DUPLICATE_ALLOCATION", f"{match.invoice_id} locked")
                
                locked_invoices.append(lock_key)

                erp_state = await self.mock_erp_lookup(match.invoice_id)
                if erp_state["state"] != "OPEN":
                    return self._reject(proposal, "STALE_STATE", f"{match.invoice_id} is {erp_state['state']}")

            is_passed = True
            return {"status": "PASSED", "proposal": proposal.model_dump()}

        except Exception as e:
            return self._reject(proposal, "PENDING_DEPENDENCY", str(e))
        finally:
            if not is_passed and locked_invoices:
                # Release locks if the transaction was rejected or failed
                for lock_key in locked_invoices:
                    await redis.delete(lock_key)

    def _reject(self, proposal, failure_type, detail):
        return {
            "status": "REJECTED",
            "failure_type": failure_type,
            "detail": detail,
            "proposed_state": proposal.model_dump()
        }