import os
import secrets
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from config import AUTO_SPEND_USD, DEFAULT_MISSION
from db import init_db, list_runs
from engine import run_mission

load_dotenv()
USER=os.getenv("JD_ADMIN_USER")
PASSWORD=os.getenv("JD_ADMIN_PASSWORD")
SESSION_SECRET=os.getenv("JD_SESSION_SECRET")
if not USER or not PASSWORD or not SESSION_SECRET:
    # The web UI remains available so configuration errors are obvious instead of crashing.
    pass

app=FastAPI(title="JD Capital")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET or secrets.token_urlsafe(32), https_only=False, same_site="lax")

LOGIN="""<!doctype html><html lang='es'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>JD Capital</title><style>body{font-family:system-ui;background:#f4f6f8}.box{max-width:380px;margin:14vh auto;background:#fff;padding:24px;border-radius:18px}input,button{width:100%;box-sizing:border-box;padding:12px;margin-top:10px;border-radius:10px;border:1px solid #ddd}button{background:#111827;color:#fff;font-weight:700}</style><div class='box'><h1>JD Capital</h1><p>Acceso privado.</p><form method='post' action='/login'><input name='username' placeholder='Usuario'><input name='password' type='password' placeholder='Contraseña'><button>Ingresar</button></form></div>"""

INDEX="""<!doctype html><html lang='es'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>JD Capital</title><style>body{font-family:system-ui;margin:0;background:#f4f6f8;color:#111827}.wrap{max-width:980px;margin:auto;padding:18px}.card{background:#fff;padding:18px;border-radius:18px;margin:14px 0;box-shadow:0 2px 15px #0001}textarea{width:100%;min-height:170px;box-sizing:border-box;padding:12px;font:inherit;border:1px solid #ddd;border-radius:12px}button{background:#111827;color:#fff;border:0;border-radius:10px;padding:11px 15px;font-weight:700}.metric{font-size:28px;font-weight:800}.muted{color:#6b7280}.error{color:#b91c1c;white-space:pre-wrap}.ok{white-space:pre-wrap;line-height:1.55}</style><div class='wrap'><div class='muted'>PRIVATE WEALTH SYSTEM</div><h1>JD Capital</h1><div class='card'><div class='muted'>Gasto automático</div><div class='metric'>$0</div></div><div class='card'><h2>Primera misión</h2><textarea id='m'>"""+DEFAULT_MISSION+"""</textarea><button onclick='run()'>▶ Ejecutar misión</button><div id='out'></div></div><div class='card'><h2>Historial</h2><div id='hist'>Cargando...</div></div><form method='post' action='/logout'><button>Cerrar sesión</button></form></div><script>async function run(){let o=document.getElementById('out');o.className='';o.textContent='Investigando en la nube...';try{let r=await fetch('/api/mission',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({mission:document.getElementById('m').value})});let d=await r.json();if(!r.ok)throw Error(d.detail||'Error');o.className='ok';o.textContent=d.result;load()}catch(e){o.className='error';o.textContent='Error: '+e.message}}async function load(){let r=await fetch('/api/runs');let d=await r.json();document.getElementById('hist').innerHTML=d.runs.length?d.runs.map(x=>'<div style="padding:8px 0;border-bottom:1px solid #eee"><b>'+x.status+'</b> '+x.created_at+'</div>').join(''):'Sin ejecuciones.'}load()</script>"""

def auth(request): return request.session.get("user")==USER

@app.on_event("startup")
def startup(): init_db()

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/login",response_class=HTMLResponse)
def login(): return LOGIN

@app.post("/login")
def do_login(request:Request, username:str=Form(...), password:str=Form(...)):
    if USER and PASSWORD and secrets.compare_digest(username,USER) and secrets.compare_digest(password,PASSWORD):
        request.session["user"]=USER; return RedirectResponse("/",303)
    return HTMLResponse(LOGIN+"<p style='color:#b91c1c'>Usuario o contraseña incorrectos.</p>",401)

@app.post("/logout")
def logout(request:Request): request.session.clear(); return RedirectResponse("/login",303)

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    if not USER or not PASSWORD or not SESSION_SECRET:
        return HTMLResponse("<h2>Configuración incompleta</h2><p>Faltan JD_ADMIN_USER, JD_ADMIN_PASSWORD o JD_SESSION_SECRET en Railway.</p>",500)
    if not auth(request): return RedirectResponse("/login",303)
    return INDEX

@app.get("/api/runs")
def runs(request:Request):
    if not auth(request): return JSONResponse({"detail":"No autorizado"},401)
    return {"runs":list_runs()}

@app.post("/api/mission")
async def mission(request:Request):
    if not auth(request): return JSONResponse({"detail":"No autorizado"},401)
    data=await request.json(); text=(data.get("mission") or DEFAULT_MISSION).strip()
    if not text: return JSONResponse({"detail":"La misión está vacía."},400)
    try: return {"result":run_mission(text)}
    except Exception as exc: return JSONResponse({"detail":f"{type(exc).__name__}: {exc}"},500)
