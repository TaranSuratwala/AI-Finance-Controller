import aiosqlite
import json
from datetime import datetime
import os

DB_PATH = "audit_ledger.db"

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
                ai_proposal JSON
            )
        ''')
        await conn.commit()

async def log_transaction(settlement_id: str, status: str, failure_reason: str, details: str, proposal_dict: dict):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            INSERT INTO audit_log (timestamp, settlement_id, status, failure_reason, details, ai_proposal)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.utcnow().isoformat(),
            settlement_id,
            status,
            failure_reason,
            details,
            json.dumps(proposal_dict)
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
