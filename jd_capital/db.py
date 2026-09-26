from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from typing import Any

from .config import DATABASE_URL
from .persistence.database import connect_sqlite as _connect_sqlite
from .persistence.database import execute as _execute
from .persistence.database import is_postgres as _is_postgres
from .persistence.database import query as _query

SCHEMA_VERSION = 4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    if _is_postgres():
        _init_postgres()
    else:
        _init_sqlite()


def _init_sqlite() -> None:
    con = _connect_sqlite()
    try:
        # Create the metadata table first. Legacy databases may already contain
        # tables with the old FLOAT schema, so migration happens BEFORE any
        # CREATE TABLE that could mask the old structure.
        con.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

        _migrate_transactions(con)
        _migrate_opportunities(con)
        _migrate_jobs(con)
        _migrate_runs(con)

        con.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('income','expense','deposit','withdrawal')),
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                note TEXT NOT NULL
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT NOT NULL,
                expected_usd_cents INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT ''
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                mission TEXT NOT NULL,
                provider_response_id TEXT,
                result TEXT,
                error TEXT
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                mission TEXT NOT NULL,
                result TEXT,
                status TEXT NOT NULL,
                job_id INTEGER
            )"""
        )
        from .persistence.migrations.financial_v1 import apply as apply_financial_v1

        apply_financial_v1(con)
        con.execute(
            "INSERT INTO app_meta(key,value) VALUES('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        con.commit()
    finally:
        con.close()


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def _migrate_transactions(con: sqlite3.Connection) -> None:
    if not _table_exists(con, 'transactions'):
        return
    cols = _table_columns(con, 'transactions')
    if 'amount' not in cols or 'amount_cents' in cols:
        return
    con.execute('ALTER TABLE transactions RENAME TO transactions_legacy')
    con.execute("""CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('income','expense','deposit','withdrawal')),
        amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
        note TEXT NOT NULL
    )""")
    rows = con.execute('SELECT id,created_at,kind,amount,note FROM transactions_legacy ORDER BY id').fetchall()
    for row in rows:
        try:
            cents = _to_cents(row[3])
        except ValueError:
            continue
        if cents > 0 and row[2] in ('income','expense','deposit','withdrawal'):
            con.execute('INSERT INTO transactions(id,created_at,kind,amount_cents,note) VALUES(?,?,?,?,?)',
                         (row[0], row[1], row[2], cents, row[4] or ''))
    # Keep the original rows as an immutable migration archive. This preserves
    # exact legacy values even when an old row cannot satisfy the normalized
    # v2 constraints; no balance is invented to compensate for bad input.
    con.execute('ALTER TABLE transactions_legacy RENAME TO transactions_v1_archive')


def _migrate_opportunities(con: sqlite3.Connection) -> None:
    if not _table_exists(con, 'opportunities'):
        return
    cols = _table_columns(con, 'opportunities')
    if 'expected_usd' in cols and 'expected_usd_cents' not in cols:
        con.execute('ALTER TABLE opportunities RENAME TO opportunities_legacy')
        con.execute("""CREATE TABLE opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            name TEXT NOT NULL, platform TEXT NOT NULL, status TEXT NOT NULL,
            expected_usd_cents INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT ''
        )""")
        rows = con.execute('SELECT id,created_at,name,platform,status,expected_usd,note FROM opportunities_legacy ORDER BY id').fetchall()
        for row in rows:
            val = row[5]
            cents = 0
            try:
                cents = int(Decimal(str(val)).quantize(Decimal('0.01')) * 100) if val is not None else 0
            except (InvalidOperation, ValueError, TypeError):
                cents = 0
            con.execute('INSERT INTO opportunities(id,created_at,name,platform,status,expected_usd_cents,note,source_url) VALUES(?,?,?,?,?,?,?,?)',
                         (row[0],row[1],row[2],row[3] or '',row[4] or 'investigar',max(0,cents),row[6] or '', ''))
        con.execute('ALTER TABLE opportunities_legacy RENAME TO opportunities_v1_archive')
    else:
        cols = _table_columns(con, 'opportunities')
        if 'source_url' not in cols:
            con.execute("ALTER TABLE opportunities ADD COLUMN source_url TEXT NOT NULL DEFAULT ''")


def _migrate_jobs(con: sqlite3.Connection) -> None:
    if not _table_exists(con, 'jobs'):
        return
    cols = _table_columns(con, 'jobs')
    if 'updated_at' not in cols:
        con.execute('ALTER TABLE jobs ADD COLUMN updated_at TEXT')
        con.execute('UPDATE jobs SET updated_at=created_at WHERE updated_at IS NULL')
    if 'provider_response_id' not in _table_columns(con, 'jobs'):
        con.execute('ALTER TABLE jobs ADD COLUMN provider_response_id TEXT')


def _migrate_runs(con: sqlite3.Connection) -> None:
    if not _table_exists(con, 'runs'):
        return
    if 'job_id' not in _table_columns(con, 'runs'):
        con.execute('ALTER TABLE runs ADD COLUMN job_id INTEGER')


def _init_postgres() -> None:
    import psycopg

    with psycopg.connect(DATABASE_URL) as con:
        with con.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    amount_cents BIGINT NOT NULL CHECK(amount_cents > 0),
                    note TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS opportunities (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expected_usd_cents BIGINT NOT NULL DEFAULT 0,
                    note TEXT NOT NULL,
                    source_url TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mission TEXT NOT NULL,
                    provider_response_id TEXT,
                    result TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    mission TEXT NOT NULL,
                    result TEXT,
                    status TEXT NOT NULL,
                    job_id BIGINT
                );
                INSERT INTO app_meta(key,value) VALUES(%s,%s)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value;
                """,
                ("schema_version", str(SCHEMA_VERSION)),
            )


def _to_cents(value: Any) -> int:
    try:
        dec = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Importe inválido")
    if dec <= 0:
        raise ValueError("El importe debe ser mayor que 0")
    return int(dec * 100)


def has_user() -> bool:
    rows = _query("SELECT id FROM users LIMIT 1")
    return bool(rows)


def create_user(username: str, password_hash: str) -> None:
    username = username.strip()
    if not username or not password_hash:
        raise ValueError("Usuario y contraseña son obligatorios")
    _execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)", (username, password_hash, utc_now()))


def get_user(username: str) -> dict[str, Any] | None:
    rows = _query("SELECT id,username,password_hash,created_at FROM users WHERE username=?", (username.strip(),))
    return _row_dict(rows[0]) if rows else None


def add_transaction(kind: str, amount: Any, note: str, idempotency_key: str | None = None) -> None:
    if kind not in ("income", "expense", "deposit", "withdrawal"):
        raise ValueError("Tipo de movimiento inválido")
    note = (note or "").strip()
    if _is_postgres():
        cents = _to_cents(amount)
        if kind == "withdrawal":
            current = metrics()["balance"]
            if cents > int(current * Decimal(100)):
                raise ValueError("El retiro supera el saldo disponible de JD Capital.")
        _execute("INSERT INTO transactions(created_at,kind,amount_cents,note) VALUES(?,?,?,?)", (utc_now(), kind, cents, note))
        return
    from .financial.services import FinancialService, generated_idempotency_key

    service = FinancialService()
    cash = service.create_account("REAL", "Legacy cash (unspecified)", "cash", provider="legacy", allow_negative=False)
    equity = service.get_or_create_system_account("REAL", "Legacy owner equity", "owner_equity")
    revenue = service.get_or_create_system_account("REAL", "Legacy generated revenue", "revenue")
    expense_account = service.get_or_create_system_account("REAL", "Legacy operating expense", "expense")
    key = idempotency_key or generated_idempotency_key("compatibility")
    if kind == "deposit":
        service.owner_contribution("REAL", cash, equity, amount, key, note)
    elif kind == "income":
        service.income("REAL", cash, revenue, amount, key, note)
    elif kind == "expense":
        service.expense("REAL", cash, expense_account, amount, key, note)
    else:
        try:
            service.personal_withdrawal("REAL", cash, equity, amount, key, note)
        except ValueError as exc:
            if "saldo disponible" in str(exc):
                raise ValueError("El retiro supera el saldo disponible de JD Capital.") from exc
            raise


def list_transactions(limit: int = 100) -> list[dict[str, Any]]:
    if not _is_postgres():
        from .financial.services import FinancialService

        kind_map = {"owner_contribution": "deposit", "personal_withdrawal": "withdrawal"}
        output = []
        for transaction in FinancialService().list_transactions("REAL", limit):
            first = transaction["entries"][0]
            output.append({
                "created_at": transaction["effective_at"],
                "kind": kind_map.get(transaction["type"], transaction["type"]),
                "amount": abs(Decimal(first["amount"])),
                "note": transaction["description"],
            })
        return output
    rows = _query(
        "SELECT created_at,kind,amount_cents,note FROM transactions ORDER BY id DESC LIMIT ?",
        (max(1, min(int(limit), 500)),),
    )
    return [{**_row_dict(r), "amount": Decimal(r["amount_cents"]) / Decimal(100)} for r in rows]


def metrics() -> dict[str, Decimal]:
    if not _is_postgres():
        from .financial.services import FinancialService

        exact = FinancialService().compatibility_metrics("REAL")
        return {key: Decimal(value) for key, value in exact.items()}
    rows = _query("SELECT kind,COALESCE(SUM(amount_cents),0) total FROM transactions GROUP BY kind")
    totals = {r["kind"]: int(r["total"] or 0) for r in rows}
    income = totals.get("income", 0) + totals.get("deposit", 0)
    expense = totals.get("expense", 0) + totals.get("withdrawal", 0)
    return {
        "balance": Decimal(income - expense) / Decimal(100),
        "income": Decimal(income) / Decimal(100),
        "expense": Decimal(expense) / Decimal(100),
        "net": Decimal(income - expense) / Decimal(100),
    }


def _validate_source_url(source_url: str) -> str:
    value = (source_url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL de fuente debe comenzar con http:// o https://")
    return value


def add_opportunity(name: str, platform: str, status: str, expected_usd: Any, note: str, source_url: str = "") -> None:
    if not (name or "").strip():
        raise ValueError("El nombre es obligatorio")
    cents = 0 if str(expected_usd).strip() in ("", "0", "0.0", "0.00") else _to_cents(expected_usd)
    source_url = _validate_source_url(source_url)
    _execute(
        "INSERT INTO opportunities(created_at,name,platform,status,expected_usd_cents,note,source_url) VALUES(?,?,?,?,?,?,?)",
        (utc_now(), name.strip(), (platform or "").strip(), (status or "investigar").strip(), cents, (note or "").strip(), source_url),
    )


def list_opportunities(limit: int = 100) -> list[dict[str, Any]]:
    rows = _query(
        "SELECT created_at,name,platform,status,expected_usd_cents,note,source_url FROM opportunities ORDER BY id DESC LIMIT ?",
        (max(1, min(int(limit), 500)),),
    )
    out = []
    for r in rows:
        d = _row_dict(r)
        d["expected_usd"] = Decimal(d.pop("expected_usd_cents")) / Decimal(100)
        out.append(d)
    return out


def create_job(mission: str) -> int:
    now = utc_now()
    _execute(
        "INSERT INTO jobs(created_at,updated_at,status,mission) VALUES(?,?,?,?)",
        (now, now, "queued", mission),
    )
    row = _query("SELECT id FROM jobs ORDER BY id DESC LIMIT 1")[0]
    return int(row["id"])


def update_job(job_id: int, status: str, result: str | None = None, error: str | None = None, provider_response_id: str | None = None) -> None:
    _execute(
        "UPDATE jobs SET updated_at=?, status=?, result=?, error=?, provider_response_id=COALESCE(?,provider_response_id) WHERE id=?",
        (utc_now(), status, result, error, provider_response_id, job_id),
    )


def get_job(job_id: int) -> dict[str, Any] | None:
    rows = _query("SELECT id,created_at,updated_at,status,mission,provider_response_id,result,error FROM jobs WHERE id=?", (job_id,))
    return _row_dict(rows[0]) if rows else None


def stale_jobs() -> list[dict[str, Any]]:
    rows = _query("SELECT id,status,mission FROM jobs WHERE status IN ('running','queued')")
    return [_row_dict(r) for r in rows]


def save_run(mission: str, result: str | None, status: str, job_id: int | None = None) -> None:
    _execute(
        "INSERT INTO runs(created_at,mission,result,status,job_id) VALUES(?,?,?,?,?)",
        (utc_now(), mission, result, status, job_id),
    )


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    rows = _query(
        "SELECT created_at,mission,result,status,job_id FROM runs ORDER BY id DESC LIMIT ?",
        (max(1, min(int(limit), 500)),),
    )
    return [_row_dict(r) for r in rows]


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return dict(row)
    if isinstance(row, dict):
        return dict(row)
    return dict(zip(row.keys(), row)) if hasattr(row, 'keys') else dict(row)
