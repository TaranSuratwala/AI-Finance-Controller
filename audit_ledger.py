import aiosqlite
import json
from datetime import datetime, timedelta
from decimal import Decimal
import os
import hashlib

DB_PATH = "audit_ledger.db"


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                settlement_id TEXT NOT NULL,
                status TEXT NOT NULL,
                failure_reason TEXT,
                details TEXT,
                ai_proposal JSON,
                merchant_id TEXT DEFAULT 'default_merchant'
            )
        ''')
        # --- Schema migration: add merchant_id to old audit_log tables ---
        cursor = await conn.execute("PRAGMA table_info(audit_log)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "merchant_id" not in columns:
            await conn.execute(
                "ALTER TABLE audit_log ADD COLUMN merchant_id TEXT DEFAULT 'default_merchant'"
            )
        if "resolution_status" not in columns:
            await conn.execute(
                "ALTER TABLE audit_log ADD COLUMN resolution_status TEXT DEFAULT 'PENDING'"
            )
        if "action_taken" not in columns:
            await conn.execute(
                "ALTER TABLE audit_log ADD COLUMN action_taken TEXT"
            )
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transit_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                settlement_id TEXT NOT NULL,
                invoice_id TEXT NOT NULL,
                amount REAL NOT NULL,
                transit_status TEXT NOT NULL,
                expected_settle_date TEXT,
                actual_settle_date TEXT,
                merchant_id TEXT DEFAULT 'default_merchant'
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS compliance_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TEXT NOT NULL,
                merchant_id TEXT NOT NULL,
                report_json TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                verification_hash TEXT NOT NULL
            )
        ''')
        await conn.commit()


async def log_transaction(settlement_id: str, status: str, failure_reason: str,
                          details: str, proposal_dict: dict, merchant_id: str = "default_merchant"):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            INSERT INTO audit_log (timestamp, settlement_id, status, failure_reason, details, ai_proposal, merchant_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.utcnow().isoformat(),
            settlement_id,
            status,
            failure_reason,
            details,
            json.dumps(proposal_dict, cls=DecimalEncoder),
            merchant_id,
        ))
        await conn.commit()


async def get_recent_rejections(limit: int = 50):
    if not os.path.exists(DB_PATH):
        return []

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute('''
            SELECT * FROM audit_log
            WHERE status = 'REJECTED'
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,)) as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]
            return rows


# ---------------------------------------------------------------------------
# Transit Ledger Functions
# ---------------------------------------------------------------------------

async def log_transit_event(settlement_id: str, invoice_id: str, amount: float,
                            transit_status: str, expected_settle_date: str,
                            actual_settle_date: str = None,
                            merchant_id: str = "default_merchant"):
    """Upsert transit status per settlement+invoice."""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Check if entry exists
        async with conn.execute(
            'SELECT id FROM transit_ledger WHERE settlement_id = ? AND invoice_id = ?',
            (settlement_id, invoice_id)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            await conn.execute('''
                UPDATE transit_ledger
                SET transit_status = ?, actual_settle_date = ?, timestamp = ?
                WHERE settlement_id = ? AND invoice_id = ?
            ''', (transit_status, actual_settle_date, datetime.utcnow().isoformat(),
                  settlement_id, invoice_id))
        else:
            await conn.execute('''
                INSERT INTO transit_ledger
                (timestamp, settlement_id, invoice_id, amount, transit_status,
                 expected_settle_date, actual_settle_date, merchant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.utcnow().isoformat(), settlement_id, invoice_id,
                  amount, transit_status, expected_settle_date, actual_settle_date,
                  merchant_id))
        await conn.commit()


async def get_transit_items(merchant_id: str = "default_merchant", status_filter: str = None):
    """Return transit ledger rows, optionally filtered by status."""
    if not os.path.exists(DB_PATH):
        return []

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        if status_filter:
            query = 'SELECT * FROM transit_ledger WHERE merchant_id = ? AND transit_status = ? ORDER BY timestamp DESC'
            params = (merchant_id, status_filter)
        else:
            query = 'SELECT * FROM transit_ledger WHERE merchant_id = ? ORDER BY timestamp DESC'
            params = (merchant_id,)
        async with conn.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_transit_summary(merchant_id: str = "default_merchant") -> dict:
    """Return aggregated cash-flow snapshot from transit ledger."""
    if not os.path.exists(DB_PATH):
        return {"settled": 0, "in_transit": 0, "refund_pending": 0, "late_credits": 0, "by_day": {}}

    today = datetime.utcnow().date()
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            'SELECT * FROM transit_ledger WHERE merchant_id = ?', (merchant_id,)
        ) as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]

    settled = 0.0
    in_transit = 0.0
    refund_pending = 0.0
    late_credits = 0.0
    by_day = {}

    for row in rows:
        amt = row["amount"]
        status = row["transit_status"]
        if status == "SETTLED":
            settled += amt
        elif status == "REFUND_PENDING":
            refund_pending += amt
        elif status == "REFUND_COMPLETE":
            pass  # already resolved
        elif status in ("INITIATED", "IN_TRANSIT"):
            in_transit += amt
            # Compute T+N bucket
            try:
                expected = datetime.fromisoformat(row["expected_settle_date"]).date()
                delta = (expected - today).days
                bucket = f"T+{max(0, delta)}"
                by_day[bucket] = by_day.get(bucket, 0.0) + amt
                if delta < 0:
                    late_credits += amt
            except (TypeError, ValueError):
                by_day["T+?"] = by_day.get("T+?", 0.0) + amt

    return {
        "settled": round(settled, 2),
        "in_transit": round(in_transit, 2),
        "refund_pending": round(refund_pending, 2),
        "late_credits": round(late_credits, 2),
        "by_day": by_day,
    }


# ---------------------------------------------------------------------------
# Compliance Report Functions
# ---------------------------------------------------------------------------

async def get_audit_records_for_period(merchant_id: str, period_start: str, period_end: str):
    """Fetch all audit_log rows for a merchant within a date range."""
    if not os.path.exists(DB_PATH):
        return []

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute('''
            SELECT * FROM audit_log
            WHERE merchant_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        ''', (merchant_id, period_start, period_end)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def store_compliance_report(merchant_id: str, report_json: str,
                                   period_start: str, period_end: str,
                                   verification_hash: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            INSERT INTO compliance_reports
            (generated_at, merchant_id, report_json, period_start, period_end, verification_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.utcnow().isoformat(), merchant_id, report_json,
              period_start, period_end, verification_hash))
        await conn.commit()


async def get_compliance_reports(merchant_id: str = "default_merchant", limit: int = 20):
    if not os.path.exists(DB_PATH):
        return []

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute('''
            SELECT * FROM compliance_reports
            WHERE merchant_id = ?
            ORDER BY generated_at DESC LIMIT ?
        ''', (merchant_id, limit)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def resolve_rejection(settlement_id: str, action_taken: str):
    """Mark a rejected transaction as resolved with the action taken."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            UPDATE audit_log
            SET resolution_status = 'RESOLVED', action_taken = ?
            WHERE settlement_id = ? AND status = 'REJECTED'
        ''', (action_taken, settlement_id))
        await conn.commit()
