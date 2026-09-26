from __future__ import annotations

import html
from functools import lru_cache
from importlib.resources import files

from ..config import APP_NAME, APP_VERSION, DEFAULT_MISSION


@lru_cache(maxsize=None)
def _asset(relative_path: str) -> str:
    return files("jd_capital.web").joinpath(relative_path).read_text(encoding="utf-8")


def page(body: str, title: str = APP_NAME) -> str:
    return (
        _asset("templates/base.html")
        .replace("__TITLE__", html.escape(title))
        .replace("__STYLES__", _asset("static/styles.css"))
        .replace("__BODY__", body)
    )


def login_page() -> str:
    return page(_asset("templates/login.html"))


def setup_page() -> str:
    return page(_asset("templates/setup.html"))


def dashboard_page(openai_configured: bool) -> str:
    status = (
        "Configurada en el almacén seguro del sistema"
        if openai_configured
        else "Falta configurar una clave de OpenAI"
    )
    body = (
        _asset("templates/dashboard.html")
        .replace("__APP_VERSION__", html.escape(APP_VERSION))
        .replace("__DEFAULT_MISSION__", html.escape(DEFAULT_MISSION))
        .replace("__OPENAI_STATUS__", html.escape(status))
        .replace("__DASHBOARD_SCRIPT__", _asset("static/dashboard.js"))
    )
    return page(body)
