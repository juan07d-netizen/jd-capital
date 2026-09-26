"""Compatibility entry point for the local FastAPI application.

The implementation lives in focused route, service and web modules. Keeping
this module preserves the public import used by existing builds and tests.
"""

from __future__ import annotations

from .application import app, create_app
from .credentials import get_openai_api_key
from .web.renderer import dashboard_page


def dashboard() -> str:
    return dashboard_page(bool(get_openai_api_key()))


__all__ = ["app", "create_app", "dashboard"]
