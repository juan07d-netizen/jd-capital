from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from ..config import DATABASE_URL, get_db_file


class LedgerInvariantError(ValueError):
    pass


class IdempotencyConflict(LedgerInvariantError):
    pass


@dataclass(frozen=True)
class Entry:
    account_id: int
    amount: str | int | Decimal
    availability_state: str = "available"
    memo: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(value: str | int | Decimal) -> Decimal:
    if isinstance(value, float):
        raise LedgerInvariantError("Los importes financieros no aceptan float.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise LedgerInvariantError("Importe inválido.") from exc
    if not result.is_finite():
        raise LedgerInvariantError("Importe inválido.")
    return result


def to_minor(value: str | int | Decimal, precision: int) -> int:
    decimal_value = _decimal(value)
    quantum = Decimal(1).scaleb(-precision)
    quantized = decimal_value.quantize(quantum)
    if decimal_value != quantized:
        raise LedgerInvariantError(f"El importe excede la precisión permitida ({precision}).")
    return int(quantized.scaleb(precision))


def from_minor(value: int, precision: int) -> str:
    return format(Decimal(value).scaleb(-precision), f".{precision}f")


class FinancialService:
    """Only authorized write boundary for the financial ledger."""

    def __init__(self, db_file: str | Path | None = None):
        if DATABASE_URL.startswith(("postgres://", "postgresql://")):
            raise NotImplementedError("Financial Core v1 requiere SQLite local; PostgreSQL se mantiene como destino futuro.")
        self.db_file = Path(db_file or get_db_file())

    def _connect(self) -> sqlite3.Connection:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_file, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def _atomic(self) -> Iterator[sqlite3.Connection]:
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def environment_id(self, code: str, con: sqlite3.Connection | None = None) -> int:
        selected = con or self._connect()
        try:
            row = selected.execute("SELECT id FROM financial_environments WHERE code=?", (code.strip().upper(),)).fetchone()
            if not row:
                raise LedgerInvariantError("Ambiente financiero inexistente.")
            return int(row[0])
        finally:
            if con is None:
                selected.close()

    def create_asset(self, code: str, name: str, asset_type: str, precision: int) -> int:
        code = code.strip().upper()
        if not code or not name.strip():
            raise LedgerInvariantError("Código y nombre del activo son obligatorios.")
        with self._atomic() as con:
            con.execute("INSERT OR IGNORE INTO financial_assets(code,name,type,precision,active) VALUES(?,?,?,?,1)", (code, name.strip(), asset_type, int(precision)))
            row = con.execute("SELECT id,type,precision FROM financial_assets WHERE code=?", (code,)).fetchone()
            if row["type"] != asset_type or int(row["precision"]) != int(precision):
                raise LedgerInvariantError("El activo ya existe con otra definición.")
            return int(row["id"])

    def create_account(
        self,
        environment: str,
        name: str,
        account_type: str,
        asset_code: str = "USD",
        *,
        provider: str = "",
        country: str | None = None,
        allow_negative: bool = False,
        integration_mode: str = "manual",
        external_reference: str | None = None,
    ) -> int:
        if not name.strip():
            raise LedgerInvariantError("El nombre de la cuenta es obligatorio.")
        with self._atomic() as con:
            environment_id = self.environment_id(environment, con)
            asset = con.execute("SELECT id FROM financial_assets WHERE code=? AND active=1", (asset_code.strip().upper(),)).fetchone()
            if not asset:
                raise LedgerInvariantError("Activo inexistente o inactivo.")
            now = utc_now()
            try:
                cursor = con.execute(
                    """INSERT INTO financial_accounts(
                        environment_id,name,type,asset_id,provider,country,allow_negative,active,
                        integration_mode,external_reference,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,1,?,?,?,?)""",
                    (environment_id, name.strip(), account_type, int(asset[0]), provider.strip(), country, int(allow_negative), integration_mode.strip(), external_reference, now, now),
                )
            except sqlite3.IntegrityError as exc:
                existing = con.execute("SELECT id,type,asset_id FROM financial_accounts WHERE environment_id=? AND name=?", (environment_id, name.strip())).fetchone()
                if existing and existing["type"] == account_type and int(existing["asset_id"]) == int(asset[0]):
                    return int(existing["id"])
                raise LedgerInvariantError("La cuenta ya existe con otra definición.") from exc
            return int(cursor.lastrowid)

    def get_or_create_system_account(self, environment: str, name: str, account_type: str, asset_code: str = "USD") -> int:
        return self.create_account(environment, name, account_type, asset_code, provider="JD Capital", allow_negative=True, integration_mode="internal")

    def _account_rows(self, con: sqlite3.Connection, account_ids: set[int]) -> dict[int, sqlite3.Row]:
        placeholders = ",".join("?" for _ in account_ids)
        rows = con.execute(
            f"""SELECT a.id,a.environment_id,a.asset_id,a.allow_negative,a.type,s.precision,s.code asset_code
                FROM financial_accounts a JOIN financial_assets s ON s.id=a.asset_id
                WHERE a.id IN ({placeholders}) AND a.active=1""",
            tuple(sorted(account_ids)),
        ).fetchall()
        result = {int(row["id"]): row for row in rows}
        if len(result) != len(account_ids):
            raise LedgerInvariantError("Una cuenta no existe o está inactiva.")
        return result

    @staticmethod
    def _request_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _current_balance_minor(self, con: sqlite3.Connection, account_id: int) -> int:
        row = con.execute(
            """SELECT COALESCE(SUM(e.amount_minor),0) balance
               FROM ledger_entries e JOIN ledger_transactions t ON t.id=e.transaction_id
               WHERE e.account_id=? AND t.status IN ('posted','settled','reversed')""",
            (account_id,),
        ).fetchone()
        return int(row["balance"] or 0)

    def _insert_entry(self, con: sqlite3.Connection, transaction_id: int, account: sqlite3.Row, amount_minor: int, state: str, memo: str) -> None:
        con.execute(
            "INSERT INTO ledger_entries(transaction_id,account_id,asset_id,amount_minor,availability_state,memo) VALUES(?,?,?,?,?,?)",
            (transaction_id, int(account["id"]), int(account["asset_id"]), amount_minor, state, memo.strip()),
        )

    def _post_with_connection(
        self,
        con: sqlite3.Connection,
        *,
        environment: str,
        transaction_type: str,
        entries: Sequence[Entry],
        idempotency_key: str,
        description: str,
        created_by: str,
        effective_at: str | None = None,
        settled_at: str | None = None,
        external_reference: str | None = None,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
        reversal_of: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[int, bool]:
        if not idempotency_key.strip():
            raise LedgerInvariantError("La idempotency key es obligatoria.")
        if len(entries) < 2:
            raise LedgerInvariantError("Una transacción requiere al menos dos asientos.")
        environment_id = self.environment_id(environment, con)
        accounts = self._account_rows(con, {entry.account_id for entry in entries})
        normalized: list[tuple[Entry, sqlite3.Row, int]] = []
        totals: dict[int, int] = {}
        account_deltas: dict[int, int] = {}
        for entry in entries:
            account = accounts[entry.account_id]
            if int(account["environment_id"]) != environment_id:
                raise LedgerInvariantError("REAL y PRUEBA no pueden compartir asientos.")
            amount_minor = to_minor(entry.amount, int(account["precision"]))
            if amount_minor == 0:
                raise LedgerInvariantError("Los asientos no pueden ser cero.")
            asset_id = int(account["asset_id"])
            totals[asset_id] = totals.get(asset_id, 0) + amount_minor
            account_deltas[entry.account_id] = account_deltas.get(entry.account_id, 0) + amount_minor
            normalized.append((entry, account, amount_minor))
        if any(total != 0 for total in totals.values()):
            raise LedgerInvariantError("La transacción no balancea por activo.")
        stable_entries = sorted(
            ({"account_id": item.account_id, "amount_minor": minor, "availability_state": item.availability_state, "memo": item.memo.strip()} for item, _, minor in normalized),
            key=lambda item: (item["account_id"], item["amount_minor"], item["availability_state"], item["memo"]),
        )
        payload = {
            "environment": environment.upper(), "type": transaction_type, "entries": stable_entries,
            "description": description.strip(), "created_by": created_by, "external_reference": external_reference,
            "source_entity_type": source_entity_type, "source_entity_id": source_entity_id,
            "reversal_of": reversal_of, "metadata": metadata or {},
        }
        if effective_at is not None:
            payload["effective_at"] = effective_at
        request_hash = self._request_hash(payload)
        existing = con.execute("SELECT id,request_hash FROM ledger_transactions WHERE environment_id=? AND idempotency_key=?", (environment_id, idempotency_key.strip())).fetchone()
        if existing:
            if existing["request_hash"] != request_hash:
                raise IdempotencyConflict("La idempotency key ya fue usada con otra operación.")
            return int(existing["id"]), False
        for account_id, delta in account_deltas.items():
            if not int(accounts[account_id]["allow_negative"]) and self._current_balance_minor(con, account_id) + delta < 0:
                raise LedgerInvariantError("La operación supera el saldo disponible de la cuenta.")
        now = utc_now()
        cursor = con.execute(
            """INSERT INTO ledger_transactions(
                environment_id,type,status,idempotency_key,request_hash,effective_at,settled_at,created_at,
                created_by,description,external_reference,source_entity_type,source_entity_id,reversal_of,metadata_json
            ) VALUES(?,?,'draft',?,?,?,?,?,?,?,?,?,?,?,?)""",
            (environment_id, transaction_type, idempotency_key.strip(), request_hash, effective_at or now, settled_at, now, created_by, description.strip(), external_reference, source_entity_type, source_entity_id, reversal_of, json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False)),
        )
        transaction_id = int(cursor.lastrowid)
        for entry, account, amount_minor in normalized:
            self._insert_entry(con, transaction_id, account, amount_minor, entry.availability_state, entry.memo)
        con.execute("UPDATE ledger_transactions SET status=? WHERE id=?", ("settled" if settled_at else "posted", transaction_id))
        con.execute(
            """INSERT INTO financial_audit_events(environment_id,actor,action,entity_type,entity_id,occurred_at,reason,correlation_id,after_json)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (environment_id, created_by, "post", "ledger_transaction", str(transaction_id), now, description.strip(), idempotency_key.strip(), json.dumps(payload, sort_keys=True, ensure_ascii=False)),
        )
        return transaction_id, True

    def post_transaction(self, **kwargs: Any) -> int:
        with self._atomic() as con:
            transaction_id, _ = self._post_with_connection(con, **kwargs)
            return transaction_id

    def _two_account_operation(self, transaction_type: str, environment: str, debit_account_id: int, credit_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str, *, debit_state: str = "available", credit_state: str = "settled", created_by: str = "user") -> int:
        positive = _decimal(amount)
        if positive <= 0:
            raise LedgerInvariantError("El importe debe ser mayor que cero.")
        return self.post_transaction(
            environment=environment, transaction_type=transaction_type,
            entries=[Entry(debit_account_id, positive, debit_state, description), Entry(credit_account_id, -positive, credit_state, description)],
            idempotency_key=idempotency_key, description=description, created_by=created_by,
        )

    def owner_contribution(self, environment: str, destination_account_id: int, owner_equity_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("owner_contribution", environment, destination_account_id, owner_equity_account_id, amount, idempotency_key, description)

    def income(self, environment: str, destination_account_id: int, revenue_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "", availability_state: str = "available") -> int:
        return self._two_account_operation("income", environment, destination_account_id, revenue_account_id, amount, idempotency_key, description, debit_state=availability_state)

    def expense(self, environment: str, source_account_id: int, expense_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("expense", environment, expense_account_id, source_account_id, amount, idempotency_key, description, debit_state="settled", credit_state="available")

    def fee(self, environment: str, source_account_id: int, fee_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("fee", environment, fee_account_id, source_account_id, amount, idempotency_key, description, debit_state="settled", credit_state="available")

    def tax(self, environment: str, source_account_id: int, tax_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("tax", environment, tax_account_id, source_account_id, amount, idempotency_key, description, debit_state="settled", credit_state="available")

    def personal_withdrawal(self, environment: str, source_account_id: int, owner_equity_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("personal_withdrawal", environment, owner_equity_account_id, source_account_id, amount, idempotency_key, description, debit_state="withdrawn", credit_state="available")

    def transfer(self, environment: str, source_account_id: int, destination_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "", *, fee: str | int | Decimal | None = None, fee_account_id: int | None = None) -> int:
        value = _decimal(amount)
        if value <= 0:
            raise LedgerInvariantError("El importe debe ser mayor que cero.")
        entries = [Entry(source_account_id, -value, "available", description), Entry(destination_account_id, value, "in_transit", description)]
        fee_value = Decimal(0) if fee is None else _decimal(fee)
        if fee_value < 0:
            raise LedgerInvariantError("La comisión no puede ser negativa.")
        if fee_value > 0:
            if fee_account_id is None:
                raise LedgerInvariantError("La comisión requiere una cuenta de gastos.")
            entries.extend([Entry(source_account_id, -fee_value, "available", "fee"), Entry(fee_account_id, fee_value, "settled", "fee")])
        return self.post_transaction(environment=environment, transaction_type="transfer", entries=entries, idempotency_key=idempotency_key, description=description, created_by="user")

    def investment_open(self, environment: str, source_account_id: int, investment_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("investment_open", environment, investment_account_id, source_account_id, amount, idempotency_key, description, debit_state="invested", credit_state="available")

    def investment_return(self, environment: str, destination_account_id: int, revenue_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("investment_return", environment, destination_account_id, revenue_account_id, amount, idempotency_key, description)

    def investment_close(self, environment: str, investment_account_id: int, destination_account_id: int, revenue_account_id: int, loss_account_id: int, principal: str | int | Decimal, result: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        principal_value, result_value = _decimal(principal), _decimal(result)
        if principal_value <= 0 or principal_value + result_value < 0:
            raise LedgerInvariantError("Cierre de inversión inválido.")
        entries = [Entry(investment_account_id, -principal_value, "invested", description), Entry(destination_account_id, principal_value + result_value, "available", description)]
        if result_value > 0:
            entries.append(Entry(revenue_account_id, -result_value, "earned", "investment return"))
        elif result_value < 0:
            entries.append(Entry(loss_account_id, -result_value, "settled", "investment loss"))
        return self.post_transaction(environment=environment, transaction_type="investment_close", entries=entries, idempotency_key=idempotency_key, description=description, created_by="user")

    def loss(self, environment: str, asset_account_id: int, loss_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "", asset_state: str = "invested") -> int:
        return self._two_account_operation("loss", environment, loss_account_id, asset_account_id, amount, idempotency_key, description, debit_state="settled", credit_state=asset_state)

    def refund(self, environment: str, destination_account_id: int, expense_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "") -> int:
        return self._two_account_operation("refund", environment, destination_account_id, expense_account_id, amount, idempotency_key, description)

    def opening_balance(self, environment: str, destination_account_id: int, equity_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "Opening balance") -> int:
        return self._two_account_operation("opening_balance", environment, destination_account_id, equity_account_id, amount, idempotency_key, description, created_by="migration")

    def legacy_migration(self, environment: str, destination_account_id: int, equity_account_id: int, amount: str | int | Decimal, idempotency_key: str, description: str = "Legacy migration") -> int:
        return self._two_account_operation("legacy_migration", environment, destination_account_id, equity_account_id, amount, idempotency_key, description, created_by="migration")

    def convert(self, environment: str, source_account_id: int, destination_account_id: int, source_clearing_account_id: int, destination_clearing_account_id: int, source_amount: str | int | Decimal, destination_amount: str | int | Decimal, rate: str | int | Decimal, rate_direction: str, quoted_at: str, source: str, idempotency_key: str, description: str = "", *, fee: str | int | Decimal | None = None, fee_account_id: int | None = None) -> int:
        source_value, destination_value, rate_value = _decimal(source_amount), _decimal(destination_amount), _decimal(rate)
        if min(source_value, destination_value, rate_value) <= 0:
            raise LedgerInvariantError("La conversión requiere importes y tasa positivos.")
        entries = [Entry(source_account_id, -source_value, "available"), Entry(source_clearing_account_id, source_value, "settled"), Entry(destination_account_id, destination_value, "available"), Entry(destination_clearing_account_id, -destination_value, "settled")]
        fee_value = Decimal(0) if fee is None else _decimal(fee)
        if fee_value < 0:
            raise LedgerInvariantError("La comisión no puede ser negativa.")
        if fee_value > 0:
            if fee_account_id is None:
                raise LedgerInvariantError("La comisión de conversión requiere una cuenta de gastos.")
            entries.extend([Entry(source_account_id, -fee_value, "available", "conversion fee"), Entry(fee_account_id, fee_value, "settled", "conversion fee")])
        with self._atomic() as con:
            transaction_id, created = self._post_with_connection(con, environment=environment, transaction_type="conversion", entries=entries, idempotency_key=idempotency_key, description=description, created_by="user", metadata={"rate": str(rate_value), "rate_direction": rate_direction, "quoted_at": quoted_at, "source": source})
            if created:
                accounts = self._account_rows(con, {source_account_id, destination_account_id})
                source_row, destination_row = accounts[source_account_id], accounts[destination_account_id]
                con.execute(
                    """INSERT INTO ledger_conversions(transaction_id,source_asset_id,source_amount_minor,destination_asset_id,destination_amount_minor,rate_decimal,rate_direction,quoted_at,source,fee_asset_id,fee_amount_minor)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (transaction_id, int(source_row["asset_id"]), to_minor(source_value, int(source_row["precision"])), int(destination_row["asset_id"]), to_minor(destination_value, int(destination_row["precision"])), str(rate_value), rate_direction, quoted_at, source, int(source_row["asset_id"]) if fee_value else None, to_minor(fee_value, int(source_row["precision"])) if fee_value else 0),
                )
            return transaction_id

    def reverse(self, transaction_id: int, idempotency_key: str, reason: str, created_by: str = "user") -> int:
        with self._atomic() as con:
            original = con.execute("SELECT * FROM ledger_transactions WHERE id=?", (transaction_id,)).fetchone()
            if not original or original["status"] not in ("posted", "settled", "reversed"):
                raise LedgerInvariantError("Sólo se puede revertir una transacción posteada.")
            existing_reversal = con.execute("SELECT id FROM ledger_transactions WHERE reversal_of=? AND status IN ('posted','settled')", (transaction_id,)).fetchone()
            if existing_reversal:
                candidate = con.execute("SELECT id,request_hash FROM ledger_transactions WHERE environment_id=? AND idempotency_key=?", (original["environment_id"], idempotency_key)).fetchone()
                if candidate and int(candidate["id"]) == int(existing_reversal["id"]):
                    return int(candidate["id"])
                raise LedgerInvariantError("La transacción ya fue revertida.")
            environment = con.execute("SELECT code FROM financial_environments WHERE id=?", (original["environment_id"],)).fetchone()[0]
            entries = [Entry(int(row["account_id"]), from_minor(-int(row["amount_minor"]), int(row["precision"])), row["availability_state"], reason) for row in con.execute("SELECT e.*,a.precision FROM ledger_entries e JOIN financial_assets a ON a.id=e.asset_id WHERE e.transaction_id=? ORDER BY e.id", (transaction_id,)).fetchall()]
            reversal_id, _ = self._post_with_connection(con, environment=environment, transaction_type="reversal", entries=entries, idempotency_key=idempotency_key, description=reason, created_by=created_by, reversal_of=transaction_id)
            con.execute("UPDATE ledger_transactions SET status='reversed' WHERE id=?", (transaction_id,))
            return reversal_id

    def reconcile(self, environment: str, account_id: int, adjustment_account_id: int, observed_balance: str | int | Decimal, observed_at: str, source: str, note: str, idempotency_key: str) -> int:
        with self._atomic() as con:
            environment_id = self.environment_id(environment, con)
            accounts = self._account_rows(con, {account_id, adjustment_account_id})
            account = accounts[account_id]
            if int(account["environment_id"]) != environment_id or int(accounts[adjustment_account_id]["environment_id"]) != environment_id:
                raise LedgerInvariantError("La conciliación no puede cruzar ambientes.")
            if int(account["asset_id"]) != int(accounts[adjustment_account_id]["asset_id"]):
                raise LedgerInvariantError("La cuenta de ajuste debe usar el mismo activo.")
            observed_minor = to_minor(observed_balance, int(account["precision"]))
            existing = con.execute("SELECT * FROM reconciliation_snapshots WHERE environment_id=? AND idempotency_key=?", (environment_id, idempotency_key)).fetchone()
            if existing:
                if (
                    int(existing["account_id"]) != account_id
                    or int(existing["observed_balance_minor"]) != observed_minor
                    or existing["observed_at"] != observed_at
                    or existing["source"] != source
                    or existing["note"] != note
                ):
                    raise IdempotencyConflict("La idempotency key de conciliación ya fue usada con otros datos.")
                return int(existing["id"])
            ledger_minor = self._current_balance_minor(con, account_id)
            difference = observed_minor - ledger_minor
            adjustment_id = None
            if difference:
                amount = from_minor(abs(difference), int(account["precision"]))
                entries = [Entry(account_id, amount if difference > 0 else f"-{amount}", "available", note), Entry(adjustment_account_id, f"-{amount}" if difference > 0 else amount, "settled", note)]
                adjustment_id, _ = self._post_with_connection(con, environment=environment, transaction_type="reconciliation_adjustment", entries=entries, idempotency_key=f"reconciliation:{idempotency_key}", description=note, created_by="reconciliation", metadata={"observed_at": observed_at, "source": source})
            cursor = con.execute("""INSERT INTO reconciliation_snapshots(environment_id,account_id,asset_id,observed_balance_minor,ledger_balance_minor,difference_minor,observed_at,source,note,idempotency_key,adjustment_transaction_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (environment_id, account_id, int(account["asset_id"]), observed_minor, ledger_minor, difference, observed_at, source, note, idempotency_key, adjustment_id))
            return int(cursor.lastrowid)

    def account_balance(self, account_id: int) -> str:
        con = self._connect()
        try:
            row = con.execute("SELECT s.precision FROM financial_accounts a JOIN financial_assets s ON s.id=a.asset_id WHERE a.id=?", (account_id,)).fetchone()
            if not row:
                raise LedgerInvariantError("Cuenta inexistente.")
            return from_minor(self._current_balance_minor(con, account_id), int(row["precision"]))
        finally:
            con.close()

    def portfolio_metrics(self, environment: str, asset_code: str = "USD") -> dict[str, str]:
        con = self._connect()
        try:
            environment_id = self.environment_id(environment, con)
            asset = con.execute("SELECT id,precision FROM financial_assets WHERE code=?", (asset_code.upper(),)).fetchone()
            if not asset:
                raise LedgerInvariantError("Activo inexistente.")
            rows = con.execute(
                """SELECT a.type,e.availability_state,COALESCE(SUM(e.amount_minor),0) amount
                   FROM ledger_entries e JOIN ledger_transactions t ON t.id=e.transaction_id
                   JOIN financial_accounts a ON a.id=e.account_id
                   WHERE t.environment_id=? AND e.asset_id=? AND t.status IN ('posted','settled','reversed')
                   GROUP BY a.type,e.availability_state""",
                (environment_id, int(asset["id"])),
            ).fetchall()
            asset_types = {"cash", "bank", "wallet", "income_platform", "investment", "exchange"}
            amounts: dict[tuple[str, str], int] = {(row["type"], row["availability_state"]): int(row["amount"]) for row in rows}
            assets_total = sum(amount for (kind, _), amount in amounts.items() if kind in asset_types)
            generated_income = -sum(amount for (kind, _), amount in amounts.items() if kind == "revenue")
            operating_cost = sum(amount for (kind, _), amount in amounts.items() if kind == "expense")
            def state_total(state: str) -> int:
                return sum(amount for (kind, availability), amount in amounts.items() if kind in asset_types and availability == state)
            precision = int(asset["precision"])
            return {
                "assets_total": from_minor(assets_total, precision),
                "liabilities_total": from_minor(0, precision),
                "net_worth": from_minor(assets_total, precision),
                "available": from_minor(state_total("available"), precision),
                "pending": from_minor(state_total("pending") + state_total("earned"), precision),
                "reserved": from_minor(state_total("reserved"), precision),
                "in_transit": from_minor(state_total("in_transit"), precision),
                "invested": from_minor(state_total("invested"), precision),
                "blocked": from_minor(state_total("blocked"), precision),
                "generated_income": from_minor(generated_income, precision),
                "realized_profit": from_minor(generated_income - operating_cost, precision),
                "operating_cost": from_minor(operating_cost, precision),
                "jd_capital_cost": from_minor(operating_cost, precision),
            }
        finally:
            con.close()

    def compatibility_metrics(self, environment: str = "REAL", asset_code: str = "USD") -> dict[str, str]:
        """Expose the v2 dashboard totals while all arithmetic remains exact."""
        con = self._connect()
        try:
            environment_id = self.environment_id(environment, con)
            asset = con.execute("SELECT id,precision FROM financial_assets WHERE code=?", (asset_code.upper(),)).fetchone()
            if not asset:
                raise LedgerInvariantError("Activo inexistente.")
            rows = con.execute(
                """SELECT t.type,COALESCE(SUM(e.amount_minor),0) amount
                   FROM ledger_transactions t JOIN ledger_entries e ON e.transaction_id=t.id
                   JOIN financial_accounts a ON a.id=e.account_id
                   WHERE t.environment_id=? AND e.asset_id=? AND t.status IN ('posted','settled','reversed')
                     AND a.type IN ('cash','bank','wallet','income_platform','investment','exchange')
                   GROUP BY t.type""",
                (environment_id, int(asset["id"])),
            ).fetchall()
            totals = {row["type"]: int(row["amount"]) for row in rows}
            income = totals.get("owner_contribution", 0) + totals.get("income", 0) + totals.get("opening_balance", 0) + totals.get("legacy_migration", 0)
            expense = -(totals.get("expense", 0) + totals.get("personal_withdrawal", 0))
            net = sum(totals.values())
            precision = int(asset["precision"])
            return {"balance": from_minor(net, precision), "income": from_minor(income, precision), "expense": from_minor(expense, precision), "net": from_minor(net, precision)}
        finally:
            con.close()

    def list_transactions(self, environment: str = "REAL", limit: int = 100) -> list[dict[str, Any]]:
        con = self._connect()
        try:
            environment_id = self.environment_id(environment, con)
            rows = con.execute("SELECT id,type,status,effective_at,description,idempotency_key,reversal_of FROM ledger_transactions WHERE environment_id=? AND status IN ('posted','settled','reversed') ORDER BY id DESC LIMIT ?", (environment_id, max(1, min(int(limit), 500)))).fetchall()
            output = []
            for row in rows:
                entries = con.execute("SELECT e.account_id,e.amount_minor,e.availability_state,s.precision,s.code asset_code FROM ledger_entries e JOIN financial_accounts a ON a.id=e.account_id JOIN financial_assets s ON s.id=e.asset_id WHERE e.transaction_id=? ORDER BY e.id", (row["id"],)).fetchall()
                output.append({**dict(row), "entries": [{"account_id": int(entry["account_id"]), "amount": from_minor(int(entry["amount_minor"]), int(entry["precision"])), "asset": entry["asset_code"], "availability_state": entry["availability_state"]} for entry in entries]})
            return output
        finally:
            con.close()


def generated_idempotency_key(prefix: str = "local") -> str:
    return f"{prefix}:{uuid.uuid4()}"
