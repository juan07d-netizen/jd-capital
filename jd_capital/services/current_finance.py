from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..db import add_transaction, list_transactions, metrics


def record_transaction(kind: str, amount: Any, note: str, idempotency_key: str | None) -> None:
    add_transaction(kind, amount, note, idempotency_key=idempotency_key)


def current_metrics() -> dict[str, str]:
    return {key: format(Decimal(value), ".2f") for key, value in metrics().items()}


def current_transactions() -> list[dict[str, Any]]:
    return [{**item, "amount": format(Decimal(item["amount"]), ".2f")} for item in list_transactions()]
