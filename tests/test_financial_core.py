from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest


def financial_service(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="jdc_financial_"))
    monkeypatch.setenv("JD_DATA_DIR", str(root))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from jd_capital.db import init_db
    from jd_capital.financial.services import FinancialService

    init_db()
    return FinancialService(), root / "jd_capital.sqlite3"


def account_set(service, environment="REAL"):
    return {
        "cash": service.create_account(environment, "Cash", "cash", allow_negative=False),
        "bank": service.create_account(environment, "Bank", "bank", allow_negative=False),
        "equity": service.get_or_create_system_account(environment, "Owner equity", "owner_equity"),
        "revenue": service.get_or_create_system_account(environment, "Revenue", "revenue"),
        "expense": service.get_or_create_system_account(environment, "Operating expense", "expense"),
        "fee": service.get_or_create_system_account(environment, "Fees", "expense"),
        "tax": service.get_or_create_system_account(environment, "Taxes", "expense"),
        "investment": service.create_account(environment, "Investment", "investment", allow_negative=False),
        "reconciliation": service.get_or_create_system_account(environment, "Reconciliation equity", "owner_equity"),
    }


def test_owner_contribution_income_and_allocation_are_distinct(monkeypatch):
    service, _ = financial_service(monkeypatch)
    accounts = account_set(service)

    contribution_id = service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "100.00", "contribution-1", "Capital inicial")
    assert service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "100.00", "contribution-1", "Capital inicial") == contribution_id
    from jd_capital.financial.services import IdempotencyConflict
    with pytest.raises(IdempotencyConflict):
        service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "101.00", "contribution-1", "Capital inicial")

    service.income("REAL", accounts["cash"], accounts["revenue"], "10.00", "income-1")
    service.expense("REAL", accounts["cash"], accounts["expense"], "3.00", "expense-1")
    service.fee("REAL", accounts["cash"], accounts["fee"], "2.00", "fee-1")
    service.tax("REAL", accounts["cash"], accounts["tax"], "1.00", "tax-1")
    service.personal_withdrawal("REAL", accounts["cash"], accounts["equity"], "4.00", "withdrawal-1")
    service.investment_open("REAL", accounts["cash"], accounts["investment"], "20.00", "investment-1")
    service.investment_return("REAL", accounts["cash"], accounts["revenue"], "2.00", "return-1")
    service.loss("REAL", accounts["investment"], accounts["expense"], "5.00", "loss-1")
    service.refund("REAL", accounts["cash"], accounts["expense"], "1.00", "refund-1")
    service.investment_close("REAL", accounts["investment"], accounts["cash"], accounts["revenue"], accounts["expense"], "15.00", "3.00", "close-1")

    metrics = service.portfolio_metrics("REAL")
    assert metrics["net_worth"] == "101.00"
    assert metrics["generated_income"] == "15.00"
    assert metrics["operating_cost"] == "10.00"
    assert metrics["invested"] == "0.00"
    assert service.account_balance(accounts["investment"]) == "0.00"


def test_transfer_preserves_net_worth_and_fee_reduces_it(monkeypatch):
    service, _ = financial_service(monkeypatch)
    accounts = account_set(service)
    service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "100.00", "seed")

    service.transfer("REAL", accounts["cash"], accounts["bank"], "30.00", "transfer-1")
    assert service.portfolio_metrics("REAL")["net_worth"] == "100.00"
    service.transfer("REAL", accounts["cash"], accounts["bank"], "10.00", "transfer-2", fee="2.00", fee_account_id=accounts["fee"])

    assert service.account_balance(accounts["cash"]) == "58.00"
    assert service.account_balance(accounts["bank"]) == "40.00"
    metrics = service.portfolio_metrics("REAL")
    assert metrics["net_worth"] == "98.00"
    assert metrics["operating_cost"] == "2.00"


def test_real_and_test_environments_are_isolated(monkeypatch):
    service, _ = financial_service(monkeypatch)
    real = account_set(service, "REAL")
    test = account_set(service, "PRUEBA")
    service.owner_contribution("REAL", real["cash"], real["equity"], "10.00", "real-seed")
    service.owner_contribution("PRUEBA", test["cash"], test["equity"], "20.00", "test-seed")

    from jd_capital.financial.services import LedgerInvariantError
    with pytest.raises(LedgerInvariantError, match="REAL y PRUEBA"):
        service.transfer("REAL", real["cash"], test["cash"], "1.00", "cross-environment")

    assert service.portfolio_metrics("REAL")["net_worth"] == "10.00"
    assert service.portfolio_metrics("PRUEBA")["net_worth"] == "20.00"


def test_partial_failure_rolls_back_entire_post(monkeypatch):
    service, db_file = financial_service(monkeypatch)
    accounts = account_set(service)
    from jd_capital.financial.services import FinancialService

    class BrokenFinancialService(FinancialService):
        calls = 0

        def _insert_entry(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("simulated interruption")
            return super()._insert_entry(*args, **kwargs)

    broken = BrokenFinancialService(db_file)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        broken.owner_contribution("REAL", accounts["cash"], accounts["equity"], "5.00", "partial")

    con = sqlite3.connect(db_file)
    assert con.execute("SELECT COUNT(*) FROM ledger_transactions WHERE idempotency_key='partial'").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0] == 0
    con.close()


def test_locked_database_does_not_create_partial_financial_data(monkeypatch):
    service, db_file = financial_service(monkeypatch)
    accounts = account_set(service)
    from jd_capital.financial.services import FinancialService

    class ShortTimeoutService(FinancialService):
        def _connect(self):
            con = sqlite3.connect(self.db_file, timeout=0.05, check_same_thread=False)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys=ON")
            return con

    lock = sqlite3.connect(db_file, timeout=1)
    lock.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            ShortTimeoutService(db_file).owner_contribution("REAL", accounts["cash"], accounts["equity"], "5.00", "locked")
    finally:
        lock.rollback()
        lock.close()

    con = sqlite3.connect(db_file)
    assert con.execute("SELECT COUNT(*) FROM ledger_transactions WHERE idempotency_key='locked'").fetchone()[0] == 0
    con.close()


def test_posted_ledger_is_balanced_and_immutable_in_database(monkeypatch):
    service, db_file = financial_service(monkeypatch)
    accounts = account_set(service)
    transaction_id = service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "10.00", "immutable")

    con = sqlite3.connect(db_file)
    con.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        con.execute("DELETE FROM ledger_transactions WHERE id=?", (transaction_id,))
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        con.execute("UPDATE ledger_entries SET amount_minor=999 WHERE transaction_id=?", (transaction_id,))
    with pytest.raises(sqlite3.IntegrityError, match="status transition"):
        con.execute("UPDATE ledger_transactions SET status='draft' WHERE id=?", (transaction_id,))
    environment_id = con.execute("SELECT id FROM financial_environments WHERE code='REAL'").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="finalized from draft"):
        con.execute("INSERT INTO ledger_transactions(environment_id,type,status,idempotency_key,request_hash,effective_at,created_at,created_by,description,metadata_json) VALUES(?,'transfer','posted','direct-post','x','2026-01-01','2026-01-01','test','bad','{}')", (environment_id,))
    con.execute("INSERT INTO ledger_transactions(environment_id,type,status,idempotency_key,request_hash,effective_at,created_at,created_by,description,metadata_json) VALUES(?,'transfer','draft','bad-balance','x','2026-01-01','2026-01-01','test','bad','{}')", (environment_id,))
    bad_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.execute("INSERT INTO ledger_entries(transaction_id,account_id,asset_id,amount_minor,availability_state,memo) SELECT ?,id,asset_id,100,'available','' FROM financial_accounts WHERE id=?", (bad_id, accounts["cash"]))
    con.execute("INSERT INTO ledger_entries(transaction_id,account_id,asset_id,amount_minor,availability_state,memo) SELECT ?,id,asset_id,100,'settled','' FROM financial_accounts WHERE id=?", (bad_id, accounts["equity"]))
    with pytest.raises(sqlite3.IntegrityError, match="not balanced"):
        con.execute("UPDATE ledger_transactions SET status='posted' WHERE id=?", (bad_id,))
    con.close()


def test_reversal_restores_balances_without_editing_original(monkeypatch):
    service, db_file = financial_service(monkeypatch)
    accounts = account_set(service)
    original = service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "12.00", "reverse-source")
    reversal = service.reverse(original, "reverse-1", "Corrección")
    assert service.reverse(original, "reverse-1", "Corrección") == reversal
    assert service.account_balance(accounts["cash"]) == "0.00"

    con = sqlite3.connect(db_file)
    assert con.execute("SELECT status FROM ledger_transactions WHERE id=?", (original,)).fetchone()[0] == "reversed"
    assert con.execute("SELECT reversal_of FROM ledger_transactions WHERE id=?", (reversal,)).fetchone()[0] == original
    con.close()


def test_conversion_preserves_original_units_rate_and_fee(monkeypatch):
    service, db_file = financial_service(monkeypatch)
    accounts = account_set(service)
    service.create_asset("BTC", "Bitcoin", "crypto", 8)
    btc = service.create_account("REAL", "BTC wallet", "wallet", "BTC")
    usd_clearing = service.get_or_create_system_account("REAL", "USD FX clearing", "clearing", "USD")
    btc_clearing = service.get_or_create_system_account("REAL", "BTC FX clearing", "clearing", "BTC")
    service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "100.00", "conversion-seed")

    transaction_id = service.convert("REAL", accounts["cash"], btc, usd_clearing, btc_clearing, "10.00", "0.00020000", "0.00002000", "BTC_per_USD", "2026-09-26T10:00:00+00:00", "manual quote", "conversion-1", fee="1.00", fee_account_id=accounts["fee"])

    assert service.account_balance(accounts["cash"]) == "89.00"
    assert service.account_balance(btc) == "0.00020000"
    assert service.portfolio_metrics("REAL", "USD")["operating_cost"] == "1.00"
    assert service.portfolio_metrics("REAL", "BTC")["net_worth"] == "0.00020000"
    con = sqlite3.connect(db_file)
    conversion = con.execute("SELECT source_amount_minor,destination_amount_minor,rate_decimal,quoted_at,source,fee_amount_minor FROM ledger_conversions WHERE transaction_id=?", (transaction_id,)).fetchone()
    assert conversion == (1000, 20000, "0.00002000", "2026-09-26T10:00:00+00:00", "manual quote", 100)
    con.close()


def test_reconciliation_records_snapshot_and_explicit_adjustment(monkeypatch):
    service, db_file = financial_service(monkeypatch)
    accounts = account_set(service)
    service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "10.00", "reconcile-seed")
    snapshot = service.reconcile("REAL", accounts["cash"], accounts["reconciliation"], "12.00", "2026-09-26T12:00:00+00:00", "manual", "Diferencia verificada", "snapshot-1")
    assert service.reconcile("REAL", accounts["cash"], accounts["reconciliation"], "12.00", "2026-09-26T12:00:00+00:00", "manual", "Diferencia verificada", "snapshot-1") == snapshot
    from jd_capital.financial.services import IdempotencyConflict
    with pytest.raises(IdempotencyConflict):
        service.reconcile("REAL", accounts["cash"], accounts["reconciliation"], "13.00", "2026-09-26T12:00:00+00:00", "manual", "Diferencia verificada", "snapshot-1")
    assert service.account_balance(accounts["cash"]) == "12.00"

    con = sqlite3.connect(db_file)
    assert con.execute("SELECT observed_balance_minor,ledger_balance_minor,difference_minor FROM reconciliation_snapshots WHERE id=?", (snapshot,)).fetchone() == (1200, 1000, 200)
    assert con.execute("SELECT COUNT(*) FROM ledger_transactions WHERE type='reconciliation_adjustment'").fetchone()[0] == 1
    con.close()


def test_transaction_status_and_availability_are_independent(monkeypatch):
    service, db_file = financial_service(monkeypatch)
    accounts = account_set(service)
    transaction_id = service.income("REAL", accounts["cash"], accounts["revenue"], "7.00", "pending-income", availability_state="pending")
    con = sqlite3.connect(db_file)
    assert con.execute("SELECT status FROM ledger_transactions WHERE id=?", (transaction_id,)).fetchone()[0] == "posted"
    states = {row[0] for row in con.execute("SELECT availability_state FROM ledger_entries WHERE transaction_id=?", (transaction_id,))}
    assert states == {"pending", "settled"}
    con.close()


def test_precision_rejects_float_and_excess_decimals(monkeypatch):
    service, _ = financial_service(monkeypatch)
    accounts = account_set(service)
    from jd_capital.financial.services import LedgerInvariantError
    with pytest.raises(LedgerInvariantError, match="float"):
        service.owner_contribution("REAL", accounts["cash"], accounts["equity"], 1.25, "float")
    with pytest.raises(LedgerInvariantError, match="precisión"):
        service.owner_contribution("REAL", accounts["cash"], accounts["equity"], "1.001", "precision")


def test_legacy_transactions_migrate_once_without_inventing_location(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="jdc_legacy_financial_"))
    monkeypatch.setenv("JD_DATA_DIR", str(root))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = root / "jd_capital.sqlite3"
    con = sqlite3.connect(db_file)
    con.executescript("""
        CREATE TABLE app_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE transactions(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,kind TEXT NOT NULL,amount_cents INTEGER NOT NULL,note TEXT NOT NULL);
        INSERT INTO transactions VALUES(1,'2026-01-01','deposit',300,'aporte');
        INSERT INTO transactions VALUES(2,'2026-01-02','income',200,'ingreso');
        INSERT INTO transactions VALUES(3,'2026-01-03','expense',50,'gasto');
        INSERT INTO transactions VALUES(4,'2026-01-04','withdrawal',100,'retiro');
    """)
    con.commit(); con.close()

    from jd_capital.db import init_db
    from jd_capital.financial.services import FinancialService
    init_db(); init_db()
    service = FinancialService()
    metrics = service.portfolio_metrics("REAL")
    assert metrics["net_worth"] == "3.50"
    assert metrics["generated_income"] == "2.00"
    assert metrics["operating_cost"] == "0.50"

    con = sqlite3.connect(db_file)
    assert con.execute("SELECT COUNT(*) FROM ledger_transactions").fetchone()[0] == 4
    assert con.execute("SELECT COUNT(*) FROM app_meta WHERE key='financial_legacy_transactions_v1'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM financial_accounts WHERE name='Legacy cash (unspecified)'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM ledger_transactions WHERE source_entity_type='legacy_transaction'").fetchone()[0] == 4
    con.close()


def test_opening_and_legacy_migration_types_are_explicit(monkeypatch):
    service, _ = financial_service(monkeypatch)
    accounts = account_set(service)
    service.opening_balance("REAL", accounts["cash"], accounts["equity"], "5.00", "opening")
    service.legacy_migration("REAL", accounts["cash"], accounts["equity"], "2.00", "legacy-opening")
    types = {transaction["type"] for transaction in service.list_transactions()}
    assert {"opening_balance", "legacy_migration"}.issubset(types)
