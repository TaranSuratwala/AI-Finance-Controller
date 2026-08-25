import fakeredis.aioredis as redis
from models import AIProposal, SettlementRecord

class RulesEngine:
    def __init__(self):
        # Using FakeRedis for local execution without needing Docker
        self.redis = redis.FakeRedis(decode_responses=True)
        self.TOLERANCE_PAISE = 50

    async def mock_erp_lookup(self, invoice_id: str):
        # Mock ERP: invoices ending in '99' are already closed (forces a failure)
        if invoice_id.endswith("99"):
            return {"state": "CLOSED"}
        return {"state": "OPEN"}

    async def evaluate(self, proposal: AIProposal, source: SettlementRecord) -> dict:
        try:
            # GATE 0: Idempotency Check (Duplicate Webhooks)
            # In a real system, we just check `await self.redis.get(source.idempotency_key)`.
            # For our synthetic testing, if the key starts with DUP_, we simulate a duplicate.
            if source.idempotency_key.startswith("DUP_"):
                return self._reject(proposal, "DUPLICATE_WEBHOOK", f"Idempotency key {source.idempotency_key} already processed.")
            
            # Record the idempotency key (simulated)
            await self.redis.set(source.idempotency_key, "processed", ex=86400)

            # GATE 1: Integer Amount Check
            total_allocated = sum(match.allocated_amount for match in proposal.proposed_matches)
            target_amount = source.amount - source.gateway_fee
            
            diff_paise = abs(int(total_allocated * 100) - int(target_amount * 100))
            if diff_paise > self.TOLERANCE_PAISE:
                return self._reject(proposal, "AMOUNT_MISMATCH", f"Diff {diff_paise} paise")

            # GATE 2 & 3: Redis Locking & State Check
            for match in proposal.proposed_matches:
                lock = await self.redis.set(f"lock:inv:{match.invoice_id}", "locked", nx=True, ex=30)
                if not lock:
                    return self._reject(proposal, "DUPLICATE_ALLOCATION", f"{match.invoice_id} locked")

                erp_state = await self.mock_erp_lookup(match.invoice_id)
                if erp_state["state"] != "OPEN":
                    return self._reject(proposal, "STALE_STATE", f"{match.invoice_id} is {erp_state['state']}")

            return {"status": "PASSED", "proposal": proposal.model_dump()}

        except Exception as e:
            return self._reject(proposal, "PENDING_DEPENDENCY", str(e))

    def _reject(self, proposal, failure_type, detail):
        return {
            "status": "REJECTED",
            "failure_type": failure_type,
            "detail": detail,
            "proposed_state": proposal.model_dump()
        }
