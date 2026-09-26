from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config import DATABASE_URL, get_db_file


def sqlite_path() -> Path:
    path = Path(get_db_file())
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect_sqlite() -> sqlite3.Connection:
    con = sqlite3.connect(sqlite_path(), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def is_postgres() -> bool:
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


def query(sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    if is_postgres():
        import psycopg
        with psycopg.connect(DATABASE_URL) as con:
            with con.cursor() as cur:
                cur.execute(sql.replace("?", "%s"), params)
                cols = [description.name for description in cur.description] if cur.description else []
                return [dict(zip(cols, row)) for row in cur.fetchall()] if cols else []
    con = connect_sqlite()
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    if is_postgres():
        import psycopg
        with psycopg.connect(DATABASE_URL) as con:
            with con.cursor() as cur:
                cur.execute(sql.replace("?", "%s"), params)
        return
    con = connect_sqlite()
    try:
        con.execute(sql, params)
        con.commit()
    finally:
        con.close()
