from __future__ import annotations

import html

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..db import create_user, get_user, has_user
from ..security import hash_password, verify_password
from ..web.renderer import login_page, page, setup_page

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login() -> str:
    return setup_page() if not has_user() else login_page()


@router.post("/setup", response_class=HTMLResponse)
async def setup(username: str = Form(...), password: str = Form(...), password2: str = Form(...)):
    if has_user():
        return RedirectResponse("/login", 303)
    if password != password2:
        return HTMLResponse(page('<div class="wrap"><div class="card"><h2>Las contraseñas no coinciden.</h2><a href="/login">Volver</a></div></div>'), 400)
    try:
        create_user(username, hash_password(password))
    except Exception as exc:
        return HTMLResponse(page(f'<div class="wrap"><div class="card"><h2>Error de configuración</h2><p>{html.escape(str(exc))}</p><a href="/login">Volver</a></div></div>'), 400)
    return RedirectResponse("/login", 303)


@router.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_user(username)
    if user and verify_password(user["password_hash"], password):
        request.session["user"] = user["username"]
        return RedirectResponse("/", 303)
    return HTMLResponse(page('<div class="wrap"><div class="card"><h2>Usuario o contraseña incorrectos.</h2><a href="/login">Volver</a></div></div>'), 401)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 303)
