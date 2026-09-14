import sqlite3
from datetime import datetime, timezone
from config import DATABASE_URL

DB_FILE = "jd_capital.sqlite3"

def _sqlite():
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS runs(
      id INTEGER PRIMARY KEY,
      created_at TEXT NOT NULL,
      mission TEXT NOT NULL,
      result TEXT,
      status TEXT NOT NULL
    );
    """
    if DATABASE_URL.startswith("postgres"):
        with __import__('psycopg').connect(DATABASE_URL) as con:
            with con.cursor() as cur:
                cur.execute(sql.replace("id INTEGER PRIMARY KEY", "id BIGSERIAL PRIMARY KEY"))
    else:
        c=_sqlite(); c.executescript(sql); c.commit(); c.close()

def save_run(mission, result, status):
    now=datetime.now(timezone.utc).isoformat()
    if DATABASE_URL.startswith("postgres"):
        with __import__('psycopg').connect(DATABASE_URL) as con:
            with con.cursor() as cur:
                cur.execute("INSERT INTO runs(created_at,mission,result,status) VALUES(%s,%s,%s,%s)",(now,mission,result,status))
    else:
        c=_sqlite(); c.execute("INSERT INTO runs(created_at,mission,result,status) VALUES(?,?,?,?)",(now,mission,result,status)); c.commit(); c.close()

def list_runs(limit=10):
    if DATABASE_URL.startswith("postgres"):
        with __import__('psycopg').connect(DATABASE_URL) as con:
            with con.cursor() as cur:
                cur.execute("SELECT created_at,mission,result,status FROM runs ORDER BY id DESC LIMIT %s",(limit,))
                return [{"created_at":r[0],"mission":r[1],"result":r[2],"status":r[3]} for r in cur.fetchall()]
    c=_sqlite(); rows=c.execute("SELECT created_at,mission,result,status FROM runs ORDER BY id DESC LIMIT ?",(limit,)).fetchall(); c.close()
    return [dict(r) for r in rows]
