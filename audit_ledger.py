import sqlite3
import json
from datetime import datetime
import os

DB_PATH = "audit_ledger.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
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
    conn.commit()
    conn.close()

def log_transaction(settlement_id: str, status: str, failure_reason: str, details: str, proposal_dict: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
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
    conn.commit()
    conn.close()

def get_recent_rejections(limit: int = 50):
    if not os.path.exists(DB_PATH):
        return []
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT * FROM audit_log 
        WHERE status = 'REJECTED' 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

# Initialize DB on import
init_db()
