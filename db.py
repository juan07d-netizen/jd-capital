import sqlite3
from datetime import datetime, timezone
from .config import DATABASE_URL, ROOT

def _sqlite():
    con = sqlite3.connect(ROOT / "data.sqlite3")
    con.row_factory = sqlite3.Row
    return con

def _pg():
    import psycopg
    return psycopg.connect(DATABASE_URL)

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS opportunities(
      id BIGSERIAL PRIMARY KEY,
      created_at TEXT NOT NULL,
      title TEXT NOT NULL,
      category TEXT,
      score DOUBLE PRECISION DEFAULT 0,
      confidence DOUBLE PRECISION DEFAULT 0,
      experiment_cost_usd DOUBLE PRECISION DEFAULT 0,
      risk TEXT,
      analysis TEXT
    );
    CREATE TABLE IF NOT EXISTS events(
      id BIGSERIAL PRIMARY KEY,
      created_at TEXT NOT NULL,
      kind TEXT NOT NULL,
      message TEXT NOT NULL
    );
    """
    if DATABASE_URL.startswith("postgres"):
        with _pg() as con:
            with con.cursor() as cur:
                cur.execute(sql)
            con.commit()
    else:
        con = _sqlite()
        con.executescript(sql.replace("BIGSERIAL", "INTEGER").replace("DOUBLE PRECISION","REAL"))
        con.commit(); con.close()

def log_event(kind, message):
    now = datetime.now(timezone.utc).isoformat()
    if DATABASE_URL.startswith("postgres"):
        with _pg() as con:
            with con.cursor() as cur:
                cur.execute("INSERT INTO events(created_at,kind,message) VALUES(%s,%s,%s)", (now, kind, message))
            con.commit()
    else:
        con = _sqlite()
        con.execute("INSERT INTO events(created_at,kind,message) VALUES(?,?,?)", (now,kind,message))
        con.commit(); con.close()

def add_opportunity(title, category, score, confidence, experiment_cost, risk, analysis):
    now = datetime.now(timezone.utc).isoformat()
    if DATABASE_URL.startswith("postgres"):
        with _pg() as con:
            with con.cursor() as cur:
                cur.execute(
                    "INSERT INTO opportunities(created_at,title,category,score,confidence,experiment_cost_usd,risk,analysis) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (now,title,category,score,confidence,experiment_cost,risk,analysis)
                )
                oid = cur.fetchone()[0]
            con.commit()
            return oid
    con = _sqlite()
    cur = con.execute(
        "INSERT INTO opportunities(created_at,title,category,score,confidence,experiment_cost_usd,risk,analysis) VALUES(?,?,?,?,?,?,?,?)",
        (now,title,category,score,confidence,experiment_cost,risk,analysis)
    )
    con.commit(); oid = cur.lastrowid; con.close(); return oid

def get_opportunities(limit=20):
    if DATABASE_URL.startswith("postgres"):
        with _pg() as con:
            with con.cursor() as cur:
                cur.execute("SELECT id,created_at,title,category,score,confidence,experiment_cost_usd,risk,analysis FROM opportunities ORDER BY score DESC,id DESC LIMIT %s",(limit,))
                cols=[d.name for d in cur.description]
                return [dict(zip(cols,row)) for row in cur.fetchall()]
    con = _sqlite()
    rows = con.execute("SELECT * FROM opportunities ORDER BY score DESC,id DESC LIMIT ?",(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_summary():
    if DATABASE_URL.startswith("postgres"):
        with _pg() as con:
            with con.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM opportunities")
                opp = cur.fetchone()[0]
        return {"opportunities":opp,"experiments":0,"revenue_usd":0,"spent_usd":0}
    con = _sqlite(); opp=con.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]; con.close()
    return {"opportunities":opp,"experiments":0,"revenue_usd":0,"spent_usd":0}
