from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..credentials import get_openai_api_key
from ..web.renderer import dashboard_page
from .dependencies import authorized

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not authorized(request):
        return RedirectResponse("/login", 303)
    return dashboard_page(bool(get_openai_api_key()))
