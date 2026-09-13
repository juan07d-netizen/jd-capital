import asyncio, base64, hashlib, hmac, os
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
from core.db import init_db, get_summary, get_opportunities, log_event
from core.engine import run_mission_once, default_mission
from core.config import AUTO_SPEND_USD

app=FastAPI(title="JD Capital Cloud")
ROOT=Path(__file__).resolve().parent
USER=os.getenv("JD_ADMIN_USER","juan")
PASSWORD=os.getenv("JD_ADMIN_PASSWORD","")
SECRET=os.getenv("JD_SESSION_SECRET","")
SCHED=os.getenv("JD_SCHEDULER_ENABLED","false").lower()=="true"
INTERVAL=max(60,int(os.getenv("JD_MISSION_INTERVAL_MINUTES","360"))*60)

def token():
    raw=USER.encode()
    sig=hmac.new(SECRET.encode(),raw,hashlib.sha256).hexdigest()
    return USER+"."+sig

def valid(t):
    if not t or "." not in t or not SECRET: return False
    u,s=t.rsplit(".",1)
    return u==USER and hmac.compare_digest(s,hmac.new(SECRET.encode(),u.encode(),hashlib.sha256).hexdigest())

def auth(req):
    if not valid(req.cookies.get("jd_session")):
        raise HTTPException(401,"authentication required")

class Mission(BaseModel):
    mission:str

@app.on_event("startup")
async def startup():
    init_db()
    log_event("startup","JD Capital Cloud started")
    if SCHED: asyncio.create_task(scheduler())

async def scheduler():
    while True:
        await asyncio.sleep(INTERVAL)
        try: await run_mission_once(default_mission(),"scheduler")
        except Exception as e: log_event("scheduler_error",str(e))

@app.get("/",response_class=HTMLResponse)
async def index(req:Request):
    try: auth(req)
    except HTTPException: return RedirectResponse("/login")
    return HTMLResponse((ROOT/"app/index.html").read_text(encoding="utf8"))

@app.get("/login",response_class=HTMLResponse)
async def login_page():
    return HTMLResponse((ROOT/"app/login.html").read_text(encoding="utf8"))

@app.post("/login")
async def login(username:str=Form(...),password:str=Form(...)):
    if not PASSWORD: return HTMLResponse("JD_ADMIN_PASSWORD no configurado",500)
    if not (hmac.compare_digest(username,USER) and hmac.compare_digest(password,PASSWORD)):
        return HTMLResponse("Credenciales incorrectas",401)
    r=RedirectResponse("/",303)
    r.set_cookie("jd_session",token(),httponly=True,secure=True,samesite="lax",max_age=604800)
    return r

@app.post("/logout")
async def logout():
    r=RedirectResponse("/login",303); r.delete_cookie("jd_session"); return r

@app.get("/api/state")
async def state(req:Request):
    auth(req)
    return {"summary":get_summary(),"opportunities":get_opportunities(20),"auto_spend_usd":AUTO_SPEND_USD}

@app.post("/api/mission")
async def mission(req:Request,payload:Mission):
    auth(req)
    if AUTO_SPEND_USD>0: raise HTTPException(403,"Auto spending is disabled.")
    try:
        return {"ok":True,"director":await run_mission_once(payload.mission,"manual")}
    except Exception as exc:
        raise HTTPException(500,f"{type(exc).__name__}: {exc}")

@app.get("/health")
async def health(): return {"ok":True}

@app.get("/manifest.webmanifest")
async def manifest():
    return JSONResponse({"name":"JD Capital","short_name":"JD Capital","start_url":"/","display":"standalone","background_color":"#f4f6f8","theme_color":"#111827","icons":[]})
