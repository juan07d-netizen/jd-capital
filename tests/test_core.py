from __future__ import annotations

import os
import json
import sqlite3
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest


def fresh_env(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="jdc_test_"))
    monkeypatch.setenv("JD_DATA_DIR", str(root))
    monkeypatch.setenv("JD_SESSION_SECRET", "test-secret-0123456789")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return root


def test_first_run_and_persistence(monkeypatch):
    root = fresh_env(monkeypatch)
    from jd_capital.db import init_db, create_user, add_transaction, metrics, add_opportunity, create_job
    from jd_capital.security import hash_password, verify_password

    init_db()
    create_user("juan", hash_password("123456789012"))
    add_transaction("deposit", "1.25", "capital inicial")
    add_transaction("income", "0.50", "primer ingreso")
    add_transaction("expense", "0.25", "prueba")
    add_opportunity("Test", "Plataforma", "investigar", "2.50", "nota")
    job_id = create_job("Misión de prueba")

    assert metrics() == {"balance": Decimal("1.50"), "income": Decimal("1.75"), "expense": Decimal("0.25"), "net": Decimal("1.50")}
    assert verify_password(__import__("jd_capital.db", fromlist=["get_user"]).get_user("juan")["password_hash"], "123456789012")
    assert job_id == 1
    assert (root / "jd_capital.sqlite3").exists()

    # Simulate restart by calling init_db again and reading all records.
    init_db()
    assert metrics()["balance"] == Decimal("1.50")


def test_legacy_migration(monkeypatch):
    root = fresh_env(monkeypatch)
    db_file = root / "jd_capital.sqlite3"
    con = sqlite3.connect(db_file)
    con.executescript("""
    CREATE TABLE runs(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, mission TEXT NOT NULL, result TEXT, status TEXT NOT NULL);
    CREATE TABLE transactions(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, amount REAL NOT NULL, note TEXT NOT NULL);
    CREATE TABLE opportunities(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, name TEXT NOT NULL, platform TEXT, status TEXT NOT NULL, expected_usd REAL DEFAULT 0, note TEXT NOT NULL);
    CREATE TABLE jobs(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, mission TEXT NOT NULL, result TEXT, error TEXT);
    INSERT INTO transactions VALUES(1,'2026-01-01','deposit',1.23,'legacy');
    INSERT INTO opportunities VALUES(1,'2026-01-01','Legacy','Platform','investigar',2.50,'legacy note');
    INSERT INTO jobs VALUES(1,'2026-01-01','queued','legacy mission',NULL,NULL);
    INSERT INTO runs VALUES(1,'2026-01-01','legacy mission','legacy result','success');
    """)
    con.commit(); con.close()

    from jd_capital.db import init_db, metrics, list_opportunities, get_job, list_runs
    init_db()
    assert metrics()["balance"] == Decimal("1.23")
    assert list_opportunities()[0]["expected_usd"] == Decimal("2.50")
    assert "updated_at" in get_job(1)
    assert "job_id" in list_runs()[0]
    con = sqlite3.connect(db_file)
    assert con.execute("SELECT amount FROM transactions_v1_archive WHERE id=1").fetchone()[0] == 1.23
    assert con.execute("SELECT expected_usd FROM opportunities_v1_archive WHERE id=1").fetchone()[0] == 2.50
    con.close()


def test_http_login_and_api(monkeypatch):
    fresh_env(monkeypatch)
    from fastapi.testclient import TestClient
    from jd_capital.app import app
    from jd_capital.db import init_db, create_user
    from jd_capital.security import hash_password

    init_db()
    create_user("juan", hash_password("123456789012"))
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200 or client.get("/").status_code == 307
        bad = client.post("/login", data={"username": "juan", "password": "bad"})
        assert bad.status_code == 401
        good = client.post("/login", data={"username": "juan", "password": "123456789012"}, follow_redirects=False)
        assert good.status_code == 303
        assert client.get("/api/metrics").status_code == 200
        headers = {"idempotency-key": "http-transaction-1"}
        created = client.post("/api/transactions", json={"kind": "deposit", "amount": "1.00", "note": "test"}, headers=headers)
        assert created.status_code == 200
        repeated = client.post("/api/transactions", json={"kind": "deposit", "amount": "1.00", "note": "test"}, headers=headers)
        assert repeated.status_code == 200
        assert client.get("/api/metrics").json()["balance"] == "1.00"


def test_openai_background_web_search_contract(monkeypatch):
    fresh_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class Resp:
        def __init__(self, status, rid="resp_test", text=None):
            self.status = status
            self.id = rid
            self.output_text = text
            self.error = None

    seen = {}

    class Responses:
        def create(self, **kwargs):
            seen.update(kwargs)
            return Resp("queued")
        def retrieve(self, rid):
            assert rid == "resp_test"
            return Resp("completed", text="Resultado de prueba con fuente")

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = Responses()

    monkeypatch.setitem(__import__("sys").modules, "openai", type("M", (), {"OpenAI": FakeClient}))
    from jd_capital.ai import run_research
    text, rid = run_research("Prueba")

    assert rid == "resp_test"
    assert "Resultado" in text
    assert seen["background"] is True
    assert seen["store"] is True
    assert seen["tools"][0]["type"] == "web_search"
    assert seen["tools"][0]["external_web_access"] is True
    assert seen["tools"][0]["user_location"]["country"] == "AR"
    assert seen["tool_choice"] == "required"


def test_job_survives_provider_error(monkeypatch):
    fresh_env(monkeypatch)
    from jd_capital.db import init_db, create_job, get_job, list_runs
    from jd_capital import engine

    init_db()
    jid = create_job("fallo controlado")

    def broken(_mission):
        raise RuntimeError("simulated provider error")

    monkeypatch.setattr(engine, "start_research", broken)
    engine.execute_job(jid, "fallo controlado")
    job = get_job(jid)
    assert job["status"] == "error"
    assert "simulated provider error" in job["error"]
    assert list_runs()[0]["status"] == "error"


def test_migration_is_idempotent(monkeypatch):
    fresh_env(monkeypatch)
    import sqlite3
    from jd_capital.db import init_db, add_transaction, metrics
    init_db()
    add_transaction("deposit", "0.01", "centavo")
    init_db()
    init_db()
    assert metrics()["balance"] == Decimal("0.01")


def test_restart_recovery_with_provider_id(monkeypatch):
    fresh_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from jd_capital.db import init_db, create_job, update_job, get_job, list_runs
    from jd_capital import engine
    init_db()
    jid = create_job("resume")
    update_job(jid, "running", provider_response_id="resp_resume")

    monkeypatch.setattr(engine, "poll_research", lambda _rid: "resultado reanudado")
    engine.resume_job(jid)
    job = get_job(jid)
    assert job["status"] == "success"
    assert job["result"] == "resultado reanudado"
    assert list_runs()[0]["status"] == "success"


def test_research_engine_accepts_replaceable_provider_without_openai(monkeypatch):
    fresh_env(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from jd_capital.db import create_job, get_job, init_db
    from jd_capital.engine import execute_job

    class FreeProvider:
        def start(self, mission):
            assert mission == "provider desacoplado"
            return "queued", "free-provider-1"

        def poll(self, response_id):
            assert response_id == "free-provider-1"
            return "resultado independiente de OpenAI"

    init_db()
    job_id = create_job("provider desacoplado")
    execute_job(job_id, "provider desacoplado", provider=FreeProvider())
    job = get_job(job_id)
    assert job["status"] == "success"
    assert job["result"] == "resultado independiente de OpenAI"


def test_reject_oversized_withdrawal_and_unsafe_source_url(monkeypatch):
    fresh_env(monkeypatch)
    from jd_capital.db import init_db, add_transaction, add_opportunity, metrics
    init_db()
    add_transaction("deposit", "1.00", "capital")
    try:
        add_transaction("withdrawal", "1.01", "no")
    except ValueError as exc:
        assert "saldo disponible" in str(exc)
    else:
        raise AssertionError("El sistema aceptó retirar más que el saldo disponible")
    try:
        add_opportunity("Bad URL", "Test", "investigar", "0", "", "javascript:alert(1)")
    except ValueError as exc:
        assert "http://" in str(exc)
    else:
        raise AssertionError("El sistema aceptó una URL no segura")
    assert metrics()["balance"] == Decimal("1.00")


def test_gui_server_logging_never_uses_standard_streams(monkeypatch):
    root = fresh_env(monkeypatch)
    import main

    called = {}

    def fake_run(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr(main.uvicorn, "run", fake_run)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    main.configure_logging()
    main.run_server(8123)

    assert called["args"] == (main.app,)
    assert called["kwargs"] == {
        "host": "127.0.0.1",
        "port": 8123,
        "log_level": "warning",
        "log_config": None,
        "access_log": False,
    }
    assert (root / "jd_capital.log").exists()


def test_research_without_api_key_is_controlled(monkeypatch):
    fresh_env(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from jd_capital.ai import AIConfigError, run_research

    with pytest.raises(AIConfigError, match="clave de OpenAI"):
        run_research("Prueba sin credenciales")


def test_keyring_credentials_are_used_when_environment_is_empty(monkeypatch):
    fresh_env(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    values = {}

    class FakeKeyring:
        @staticmethod
        def get_password(service, account):
            return values.get((service, account))

        @staticmethod
        def set_password(service, account, value):
            values[(service, account)] = value

        @staticmethod
        def delete_password(service, account):
            values.pop((service, account), None)

    monkeypatch.setitem(sys.modules, "keyring", FakeKeyring)
    from jd_capital.credentials import delete_openai_api_key, get_openai_api_key, set_openai_api_key

    set_openai_api_key("test-keyring-key")
    assert get_openai_api_key() == "test-keyring-key"
    delete_openai_api_key()
    assert get_openai_api_key() == ""


def test_windows_default_data_directory_uses_localappdata(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="jdc_localappdata_"))
    monkeypatch.delenv("JD_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(root))
    from jd_capital.config import default_data_dir

    assert default_data_dir() == root / "JD Capital"


def run_dashboard_javascript(monkeypatch) -> dict:
    fresh_env(monkeypatch)
    from jd_capital import app as app_module

    monkeypatch.setattr(app_module, "get_openai_api_key", lambda: "")
    rendered = app_module.dashboard()
    script = rendered.split("<script>", 1)[1].split("</script>", 1)[0]
    harness = r"""
const fs = require('fs');
const source = fs.readFileSync(0, 'utf8');
const elements = {};
global.document = {getElementById(id) { return elements[id] ||= {value: '', textContent: '', innerHTML: '', className: '', disabled: false, addEventListener() {}}; }};
const responses = {
  '/api/metrics': {balance: 0, income: 0, expense: 0, net: 0},
  '/api/transactions': {transactions: []},
  '/api/opportunities': {opportunities: []},
  '/api/runs': {runs: []},
  '/api/settings': {configured: false},
};
const posts = [];
global.fetch = async (url, opts = {}) => {
  if (opts.method === 'POST') posts.push({url, body: JSON.parse(opts.body), headers: opts.headers || {}});
  return {ok: true, json: async () => responses[url] || {ok: true}};
};
const alerts = [];
global.alert = message => alerts.push(String(message));
eval(source + '\nglobal.tx = tx; global.opp = opp;');
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  const element = id => document.getElementById(id);
  element('kind').value = 'deposit'; element('amount').value = '1'; element('note').value = 'Prueba inicial';
  await Promise.all([global.tx(), global.tx()]);
  element('oname').value = 'Prueba'; element('platform').value = 'Test'; element('ostatus').value = 'investigar';
  element('expected').value = '1'; element('source_url').value = ''; element('onote').value = 'Prueba inicial';
  await global.opp();
  process.stdout.write(JSON.stringify({posts, alerts}));
})().catch(error => { console.error(error); process.exit(1); });
"""
    result = subprocess.run(
        ["node", "-e", harness],
        input=script,
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def test_transaction_form_javascript_posts_entered_values(monkeypatch):
    result = run_dashboard_javascript(monkeypatch)
    transaction = next(item for item in result["posts"] if item["url"] == "/api/transactions")
    assert transaction["body"] == {"kind": "deposit", "amount": "1", "note": "Prueba inicial"}
    assert transaction["headers"]["idempotency-key"]
    assert len([item for item in result["posts"] if item["url"] == "/api/transactions"]) == 1
    assert result["alerts"] == []


def test_opportunity_form_javascript_posts_entered_values(monkeypatch):
    result = run_dashboard_javascript(monkeypatch)
    opportunity = next(item for item in result["posts"] if item["url"] == "/api/opportunities")
    assert opportunity["body"] == {
        "name": "Prueba",
        "platform": "Test",
        "status": "investigar",
        "expected_usd": "1",
        "note": "Prueba inicial",
        "source_url": "",
    }
    assert result["alerts"] == []


def test_dashboard_critical_actions_are_external_and_event_bound(monkeypatch):
    fresh_env(monkeypatch)
    from jd_capital import app as app_module

    monkeypatch.setattr(app_module, "get_openai_api_key", lambda: "")
    rendered = app_module.dashboard()
    assert "onclick=" not in rendered
    assert "saveTransactionButton').addEventListener('click', tx)" in rendered
    assert "saveOpportunityButton').addEventListener('click', opp)" in rendered
