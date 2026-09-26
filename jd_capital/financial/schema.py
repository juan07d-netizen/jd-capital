from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

FINANCIAL_SCHEMA_VERSION = 1

TRANSACTION_TYPES = (
    "owner_contribution", "income", "expense", "transfer", "investment_open",
    "investment_return", "investment_close", "loss", "fee", "refund",
    "personal_withdrawal", "tax", "conversion", "reconciliation_adjustment",
    "reversal", "opening_balance", "legacy_migration",
)
TRANSACTION_STATES = ("draft", "pending", "posted", "settled", "reversed", "cancelled", "failed")
AVAILABILITY_STATES = ("pending", "earned", "available", "reserved", "in_transit", "invested", "blocked", "settled", "withdrawn", "cancelled")
ACCOUNT_TYPES = ("cash", "bank", "wallet", "income_platform", "investment", "exchange", "clearing", "owner_equity", "expense", "revenue", "other")
ASSET_TYPES = ("fiat", "internal_unit", "crypto", "other")


def _quoted(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_financial_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS financial_environments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE CHECK(code IN ('REAL','PRUEBA')),
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS financial_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ({_quoted(ASSET_TYPES)})),
            precision INTEGER NOT NULL CHECK(precision BETWEEN 0 AND 18),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS financial_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_id INTEGER NOT NULL REFERENCES financial_environments(id),
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ({_quoted(ACCOUNT_TYPES)})),
            asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
            provider TEXT NOT NULL DEFAULT '',
            country TEXT,
            allow_negative INTEGER NOT NULL DEFAULT 0 CHECK(allow_negative IN (0,1)),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            integration_mode TEXT NOT NULL DEFAULT 'manual',
            external_reference TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(environment_id, name),
            UNIQUE(id, environment_id)
        );
        CREATE TABLE IF NOT EXISTS ledger_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_id INTEGER NOT NULL REFERENCES financial_environments(id),
            type TEXT NOT NULL CHECK(type IN ({_quoted(TRANSACTION_TYPES)})),
            status TEXT NOT NULL CHECK(status IN ({_quoted(TRANSACTION_STATES)})),
            idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            effective_at TEXT NOT NULL,
            settled_at TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            description TEXT NOT NULL,
            external_reference TEXT,
            source_entity_type TEXT,
            source_entity_id TEXT,
            reversal_of INTEGER REFERENCES ledger_transactions(id),
            metadata_json TEXT NOT NULL DEFAULT '{{}}',
            UNIQUE(environment_id, idempotency_key)
        );
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL REFERENCES ledger_transactions(id) ON DELETE RESTRICT,
            account_id INTEGER NOT NULL REFERENCES financial_accounts(id),
            asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
            amount_minor INTEGER NOT NULL CHECK(amount_minor <> 0),
            availability_state TEXT NOT NULL CHECK(availability_state IN ({_quoted(AVAILABILITY_STATES)})),
            memo TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_ledger_entries_transaction ON ledger_entries(transaction_id);
        CREATE INDEX IF NOT EXISTS idx_ledger_entries_account_asset ON ledger_entries(account_id, asset_id);
        CREATE INDEX IF NOT EXISTS idx_ledger_transactions_environment_time ON ledger_transactions(environment_id, effective_at);
        CREATE TABLE IF NOT EXISTS ledger_conversions (
            transaction_id INTEGER PRIMARY KEY REFERENCES ledger_transactions(id) ON DELETE RESTRICT,
            source_asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
            source_amount_minor INTEGER NOT NULL CHECK(source_amount_minor > 0),
            destination_asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
            destination_amount_minor INTEGER NOT NULL CHECK(destination_amount_minor > 0),
            rate_decimal TEXT NOT NULL,
            rate_direction TEXT NOT NULL,
            quoted_at TEXT NOT NULL,
            source TEXT NOT NULL,
            fee_asset_id INTEGER REFERENCES financial_assets(id),
            fee_amount_minor INTEGER NOT NULL DEFAULT 0 CHECK(fee_amount_minor >= 0)
        );
        CREATE TABLE IF NOT EXISTS reconciliation_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_id INTEGER NOT NULL REFERENCES financial_environments(id),
            account_id INTEGER NOT NULL REFERENCES financial_accounts(id),
            asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
            observed_balance_minor INTEGER NOT NULL,
            ledger_balance_minor INTEGER NOT NULL,
            difference_minor INTEGER NOT NULL,
            observed_at TEXT NOT NULL,
            source TEXT NOT NULL,
            note TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            adjustment_transaction_id INTEGER REFERENCES ledger_transactions(id),
            UNIQUE(environment_id, idempotency_key)
        );
        CREATE TABLE IF NOT EXISTS financial_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_id INTEGER REFERENCES financial_environments(id),
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT
        );

        CREATE TRIGGER IF NOT EXISTS ledger_entry_account_guard
        BEFORE INSERT ON ledger_entries
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM ledger_transactions t
                JOIN financial_accounts a ON a.id = NEW.account_id
                WHERE t.id = NEW.transaction_id
                  AND a.environment_id = t.environment_id
                  AND a.asset_id = NEW.asset_id
                  AND a.active = 1
            ) THEN RAISE(ABORT, 'ledger account/environment/asset mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS ledger_entry_account_update_guard
        BEFORE UPDATE ON ledger_entries
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM ledger_transactions t
                JOIN financial_accounts a ON a.id = NEW.account_id
                WHERE t.id = NEW.transaction_id
                  AND a.environment_id = t.environment_id
                  AND a.asset_id = NEW.asset_id
                  AND a.active = 1
            ) THEN RAISE(ABORT, 'ledger account/environment/asset mismatch') END;
        END;

        CREATE TRIGGER IF NOT EXISTS ledger_direct_post_guard
        BEFORE INSERT ON ledger_transactions
        WHEN NEW.status IN ('posted','settled','reversed')
        BEGIN SELECT RAISE(ABORT, 'ledger transactions must be finalized from draft'); END;

        CREATE TRIGGER IF NOT EXISTS ledger_post_balance_guard
        BEFORE UPDATE OF status ON ledger_transactions
        WHEN NEW.status IN ('posted','settled') AND OLD.status NOT IN ('posted','settled')
        BEGIN
            SELECT CASE WHEN (SELECT COUNT(*) FROM ledger_entries WHERE transaction_id = NEW.id) < 2
                THEN RAISE(ABORT, 'ledger transaction requires at least two entries') END;
            SELECT CASE WHEN EXISTS (
                SELECT asset_id FROM ledger_entries WHERE transaction_id = NEW.id
                GROUP BY asset_id HAVING SUM(amount_minor) <> 0
            ) THEN RAISE(ABORT, 'ledger transaction is not balanced by asset') END;
        END;

        CREATE TRIGGER IF NOT EXISTS ledger_posted_entry_insert_guard
        BEFORE INSERT ON ledger_entries
        WHEN (SELECT status FROM ledger_transactions WHERE id = NEW.transaction_id) IN ('posted','settled','reversed')
        BEGIN SELECT RAISE(ABORT, 'posted ledger entries are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS ledger_posted_entry_update_guard
        BEFORE UPDATE ON ledger_entries
        WHEN (SELECT status FROM ledger_transactions WHERE id = OLD.transaction_id) IN ('posted','settled','reversed')
        BEGIN SELECT RAISE(ABORT, 'posted ledger entries are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS ledger_posted_entry_delete_guard
        BEFORE DELETE ON ledger_entries
        WHEN (SELECT status FROM ledger_transactions WHERE id = OLD.transaction_id) IN ('posted','settled','reversed')
        BEGIN SELECT RAISE(ABORT, 'posted ledger entries are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS ledger_posted_transaction_delete_guard
        BEFORE DELETE ON ledger_transactions
        WHEN OLD.status IN ('posted','settled','reversed')
        BEGIN SELECT RAISE(ABORT, 'posted ledger transactions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS ledger_posted_transaction_update_guard
        BEFORE UPDATE ON ledger_transactions
        WHEN OLD.status IN ('posted','settled','reversed') AND (
            NEW.environment_id <> OLD.environment_id OR NEW.type <> OLD.type OR
            NEW.idempotency_key <> OLD.idempotency_key OR NEW.request_hash <> OLD.request_hash OR
            NEW.effective_at <> OLD.effective_at OR NEW.created_at <> OLD.created_at OR
            NEW.created_by <> OLD.created_by OR NEW.description <> OLD.description OR
            COALESCE(NEW.external_reference,'') <> COALESCE(OLD.external_reference,'') OR
            COALESCE(NEW.source_entity_type,'') <> COALESCE(OLD.source_entity_type,'') OR
            COALESCE(NEW.source_entity_id,'') <> COALESCE(OLD.source_entity_id,'') OR
            COALESCE(NEW.reversal_of,0) <> COALESCE(OLD.reversal_of,0) OR
            NEW.metadata_json <> OLD.metadata_json
        )
        BEGIN SELECT RAISE(ABORT, 'posted ledger transactions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS ledger_status_transition_guard
        BEFORE UPDATE OF status ON ledger_transactions
        WHEN NOT (
            NEW.status = OLD.status OR
            (OLD.status = 'draft' AND NEW.status IN ('pending','posted','settled','cancelled','failed')) OR
            (OLD.status = 'pending' AND NEW.status IN ('posted','settled','cancelled','failed')) OR
            (OLD.status = 'posted' AND NEW.status IN ('settled','reversed')) OR
            (OLD.status = 'settled' AND NEW.status = 'reversed')
        )
        BEGIN SELECT RAISE(ABORT, 'invalid ledger status transition'); END;
        CREATE TRIGGER IF NOT EXISTS financial_account_identity_guard
        BEFORE UPDATE OF environment_id,asset_id ON financial_accounts
        WHEN EXISTS(SELECT 1 FROM ledger_entries WHERE account_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'ledger account identity is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS financial_asset_precision_guard
        BEFORE UPDATE OF precision ON financial_assets
        WHEN EXISTS(SELECT 1 FROM ledger_entries WHERE asset_id=OLD.id)
        BEGIN SELECT RAISE(ABORT, 'ledger asset precision is immutable'); END;
        """
    )
    now = _utc_now()
    con.execute("INSERT OR IGNORE INTO financial_environments(code,name,created_at) VALUES('REAL','REAL',?)", (now,))
    con.execute("INSERT OR IGNORE INTO financial_environments(code,name,created_at) VALUES('PRUEBA','PRUEBA',?)", (now,))
    con.execute("INSERT OR IGNORE INTO financial_assets(code,name,type,precision,active) VALUES('USD','US Dollar','fiat',2,1)")
    con.execute(
        "INSERT INTO app_meta(key,value) VALUES('financial_schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(FINANCIAL_SCHEMA_VERSION),),
    )
    _migrate_legacy_transactions(con)


def _foundation_account(con: sqlite3.Connection, environment_id: int, asset_id: int, name: str, account_type: str, allow_negative: bool) -> int:
    now = _utc_now()
    con.execute(
        """INSERT OR IGNORE INTO financial_accounts(
            environment_id,name,type,asset_id,provider,allow_negative,active,integration_mode,created_at,updated_at
        ) VALUES(?,?,?,?,?, ?,1,'manual',?,?)""",
        (environment_id, name, account_type, asset_id, "legacy", int(allow_negative), now, now),
    )
    return int(con.execute("SELECT id FROM financial_accounts WHERE environment_id=? AND name=?", (environment_id, name)).fetchone()[0])


def _migrate_legacy_transactions(con: sqlite3.Connection) -> None:
    marker = con.execute("SELECT value FROM app_meta WHERE key='financial_legacy_transactions_v1'").fetchone()
    if marker or not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='transactions'").fetchone():
        return
    environment_id = int(con.execute("SELECT id FROM financial_environments WHERE code='REAL'").fetchone()[0])
    asset_id = int(con.execute("SELECT id FROM financial_assets WHERE code='USD'").fetchone()[0])
    cash = _foundation_account(con, environment_id, asset_id, "Legacy cash (unspecified)", "cash", False)
    equity = _foundation_account(con, environment_id, asset_id, "Legacy owner equity", "owner_equity", True)
    revenue = _foundation_account(con, environment_id, asset_id, "Legacy generated revenue", "revenue", True)
    expense = _foundation_account(con, environment_id, asset_id, "Legacy operating expense", "expense", True)
    mapping = {
        "deposit": ("owner_contribution", cash, equity, 1),
        "income": ("income", cash, revenue, 1),
        "expense": ("expense", cash, expense, -1),
        "withdrawal": ("personal_withdrawal", cash, equity, -1),
    }
    for row in con.execute("SELECT id,created_at,kind,amount_cents,note FROM transactions ORDER BY id").fetchall():
        transaction_type, cash_account, counterpart, direction = mapping.get(row[2], ("legacy_migration", cash, equity, 1))
        amount = int(row[3])
        key = f"legacy-v2-transaction:{row[0]}"
        payload = {"legacy_id": row[0], "kind": row[2], "amount_minor": amount, "created_at": row[1]}
        request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        cursor = con.execute(
            """INSERT OR IGNORE INTO ledger_transactions(
                environment_id,type,status,idempotency_key,request_hash,effective_at,created_at,created_by,
                description,source_entity_type,source_entity_id,metadata_json
            ) VALUES(?,?,'draft',?,?,?,?,?,?,?,?,?)""",
            (environment_id, transaction_type, key, request_hash, row[1], _utc_now(), "migration", row[4] or "", "legacy_transaction", str(row[0]), json.dumps({"legacy_kind": row[2], "origin": "jd_capital_v2"})),
        )
        if not cursor.rowcount:
            continue
        transaction_id = int(cursor.lastrowid)
        con.execute("INSERT INTO ledger_entries(transaction_id,account_id,asset_id,amount_minor,availability_state,memo) VALUES(?,?,?,?,?,?)", (transaction_id, cash_account, asset_id, direction * amount, "available" if direction > 0 else "withdrawn", row[4] or ""))
        con.execute("INSERT INTO ledger_entries(transaction_id,account_id,asset_id,amount_minor,availability_state,memo) VALUES(?,?,?,?,?,?)", (transaction_id, counterpart, asset_id, -direction * amount, "settled", row[4] or ""))
        con.execute("UPDATE ledger_transactions SET status='posted' WHERE id=?", (transaction_id,))
    con.execute("INSERT INTO app_meta(key,value) VALUES('financial_legacy_transactions_v1',?)", (_utc_now(),))
