from __future__ import annotations

from fastapi import Request


def authorized(request: Request) -> bool:
    return bool(request.session.get("user"))
