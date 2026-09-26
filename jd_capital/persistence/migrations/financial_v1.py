from __future__ import annotations

import sqlite3

from ...financial.schema import ensure_financial_schema


def apply(con: sqlite3.Connection) -> None:
    """Install Financial Core v1 and migrate normalized v2 movements once."""
    ensure_financial_schema(con)
