from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..db import add_opportunity, list_opportunities


def create_opportunity(data: dict[str, Any]) -> None:
    add_opportunity(
        data.get("name", ""), data.get("platform", ""), data.get("status", "investigar"),
        data.get("expected_usd", 0), data.get("note", ""), data.get("source_url", ""),
    )


def current_opportunities() -> list[dict[str, Any]]:
    return [{**item, "expected_usd": format(Decimal(item["expected_usd"]), ".2f")} for item in list_opportunities()]
