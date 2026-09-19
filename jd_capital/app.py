from __future__ import annotations

import asyncio
import html
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .config import APP_NAME, APP_VERSION, DEFAULT_MISSION
from .credentials import delete_openai_api_key, get_openai_api_key, set_openai_api_key
from .db import (
    add_opportunity,
    add_transaction,
    create_job,
    create_user,
    get_job,
    get_user,
    has_user,
    init_db,
    list_opportunities,
    list_runs,
    list_transactions,
    metrics,
    stale_jobs,
)
from .engine import execute_job, resume_job
from .session_secret import get_session_secret
from .security import hash_password, verify_password

logger = logging.getLogger(APP_NAME)
SESSION_SECRET = get_session_secret()
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jd-research")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    # Recover provider-backed jobs after a clean/restart. Jobs that never reached
    # the provider are marked as interrupted instead of being silently lost.
    for job in stale_jobs():
        if job.get("provider_response_id"):
            EXECUTOR.submit(resume_job, int(job["id"]))
        else:
            EXECUTOR.submit(resume_job, int(job["id"]))
    yield
    EXECUTOR.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=False,  # localhost only in the desktop build
    same_site="lax",
    max_age=60 * 60 * 8,
)


def authorized(request: Request) -> bool:
    return bool(request.session.get("user"))


def page(body: str, title: str = APP_NAME) -> str:
    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>
    <style>
      body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f4f6f8;color:#111827}}
      .wrap{{max-width:1180px;margin:auto;padding:24px}} .card{{background:#fff;border-radius:18px;padding:20px;margin:14px 0;box-shadow:0 2px 16px #0001}}
      .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}} .cols{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
      .metric{{font-size:30px;font-weight:800;margin-top:5px}} .muted{{color:#6b7280}} h1,h2{{margin-top:0}}
      input,select,textarea,button{{box-sizing:border-box;width:100%;padding:11px;border-radius:10px;border:1px solid #d1d5db;font:inherit;margin-top:8px}}
      textarea{{min-height:170px;resize:vertical}} button{{border:0;background:#111827;color:#fff;font-weight:700;cursor:pointer}} button.secondary{{background:#e5e7eb;color:#111827}}
      .row{{padding:11px 0;border-bottom:1px solid #eee}} .ok{{white-space:pre-wrap;line-height:1.55}} .err{{white-space:pre-wrap;color:#b91c1c}}
      .tag{{display:inline-block;background:#eef2ff;border-radius:999px;padding:3px 8px;font-size:12px}} .top{{display:flex;justify-content:space-between;align-items:center;gap:10px}}
      .status{{padding:8px 10px;border-radius:10px;background:#f3f4f6;display:inline-block;font-size:13px}} .danger{{background:#fee2e2;color:#991b1b}}
      @media(max-width:800px){{.grid,.cols{{grid-template-columns:1fr 1fr}}}} @media(max-width:540px){{.grid,.cols{{grid-template-columns:1fr}}}}
    </style></head><body>{body}</body></html>"""


LOGIN_PAGE = page("""
<div class='wrap'><div class='card' style='max-width:420px;margin:14vh auto'><h1>JD Capital</h1><p class='muted'>Acceso privado local.</p>
<form method='post' action='/login'><input name='username' placeholder='Usuario' autocomplete='username' required><input name='password' type='password' placeholder='Contraseña' autocomplete='current-password' required><button>Ingresar</button></form></div></div>
""")

SETUP_PAGE = page("""
<div class='wrap'><div class='card' style='max-width:520px;margin:8vh auto'><h1>Configuración inicial</h1><p>Creá el único usuario local de JD Capital.</p>
<form method='post' action='/setup'><input name='username' placeholder='Usuario' autocomplete='username' required><input name='password' type='password' placeholder='Contraseña (mínimo 12 caracteres)' autocomplete='new-password' required><input name='password2' type='password' placeholder='Repetir contraseña' autocomplete='new-password' required><button>Crear acceso</button></form></div></div>
""")


def dashboard() -> str:
    mission = html.escape(DEFAULT_MISSION)
    configured = bool(get_openai_api_key())
    status = "Configurada en el almacén seguro del sistema" if configured else "Falta configurar una clave de OpenAI"
    return page(f"""
<div class='wrap'>
 <div class='top'><div><div class='muted'>PRIVATE WEALTH SYSTEM · v{APP_VERSION}</div><h1>JD Capital</h1></div><form method='post' action='/logout'><button class='secondary' style='width:auto'>Cerrar sesión</button></form></div>
 <div class='grid'>
  <div class='card'><div class='muted'>Dinero disponible</div><div class='metric' id='balance'>USD 0.00</div></div>
  <div class='card'><div class='muted'>Ingresos</div><div class='metric' id='income'>USD 0.00</div></div>
  <div class='card'><div class='muted'>Gastos</div><div class='metric' id='expense'>USD 0.00</div></div>
  <div class='card'><div class='muted'>Resultado neto</div><div class='metric' id='net'>USD 0.00</div></div>
 </div>
 <div class='card'><h2>Motor de investigación</h2><p class='muted'>Investiga en la web en segundo plano y guarda el resultado. Un fallo de la IA no cierra JD Capital.</p>
 <textarea id='mission'>{mission}</textarea><button onclick='runMission()'>▶ Ejecutar investigación</button><div id='out' class='status' style='margin-top:12px'>Esperando una investigación.</div></div>
 <div class='card'><h2>Conexión IA</h2><div class='status' id='keyStatus'>{html.escape(status)}</div>
 <input id='apiKey' type='password' placeholder='Pegá aquí tu clave de API de OpenAI (no se muestra luego)'><div class='cols'>
 <button onclick='saveKey()'>Guardar clave</button><button class='secondary' onclick='removeKey()'>Eliminar clave</button></div>
 <p class='muted'>La clave se guarda en el almacén de credenciales del sistema operativo; no se escribe en el historial de investigaciones.</p></div>
 <div class='cols'>
  <div class='card'><h2>Movimientos</h2><select id='kind'><option value='deposit'>Ingresar capital</option><option value='income'>Registrar ganancia</option><option value='expense'>Registrar gasto</option><option value='withdrawal'>Retirar</option></select><input id='amount' type='number' step='0.01' min='0.01' placeholder='USD'><input id='note' placeholder='Concepto'><button onclick='tx()'>Guardar movimiento</button><div id='txs'></div></div>
  <div class='card'><h2>Oportunidades</h2><input id='oname' placeholder='Nombre'><input id='platform' placeholder='Plataforma'><select id='ostatus'><option>investigar</option><option>validar</option><option>activa</option><option>descartada</option></select><input id='expected' type='number' step='0.01' min='0' placeholder='USD esperados (opcional)'><input id='source_url' placeholder='URL fuente (opcional)'><input id='onote' placeholder='Nota'><button onclick='opp()'>Guardar oportunidad</button><div id='opps'></div></div>
 </div>
 <div class='card'><h2>Historial de investigaciones</h2><div id='hist'>Cargando...</div></div>
</div>
<script>
const $=id=>document.getElementById(id); const money=x=>'USD '+Number(x||0).toFixed(2);
function esc(v){{return String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;')}}
async function json(url,opts){{const r=await fetch(url,opts);let d={{}};try{{d=await r.json()}}catch{{}};if(!r.ok)throw new Error(d.detail||'Error inesperado');return d}}
async function load(){{try{{const m=await json('/api/metrics');$('balance').textContent=money(m.balance);$('income').textContent=money(m.income);$('expense').textContent=money(m.expense);$('net').textContent=money(m.net);
const t=await json('/api/transactions');$('txs').innerHTML=t.transactions.length?t.transactions.map(x=>`<div class='row'><b>${{esc(x.kind)}}</b> ${{money(x.amount)}}<br><span class='muted'>${{esc(x.note)}}</span></div>`).join(''):'<p class="muted">Sin movimientos.</p>';
const o=await json('/api/opportunities');$('opps').innerHTML=o.opportunities.length?o.opportunities.map(x=>`<div class='row'><b>${{esc(x.name)}}</b> <span class='tag'>${{esc(x.status)}}</span><br>${{esc(x.platform||'')}}<br><span class='muted'>${{esc(x.note||'')}}</span>${{x.source_url?`<br><a href='${{esc(x.source_url)}}' target='_blank' rel='noreferrer noopener'>Fuente</a>`:''}}</div>`).join(''):'<p class="muted">Sin oportunidades.</p>';
const h=await json('/api/runs');$('hist').innerHTML=h.runs.length?h.runs.map(x=>`<div class='row'><b>${{esc(x.status)}}</b> · ${{esc(x.created_at)}}<br>${{x.status==='success'?'<details><summary>Ver investigación</summary><div class="ok">'+esc(x.result||'')+'</div></details>':'<span class="muted">'+esc(x.result||'')+'</span>'}}</div>`).join(''):'<p class="muted">Sin investigaciones.</p>';
const s=await json('/api/settings');$('keyStatus').textContent=s.configured?'Configurada en el almacén seguro del sistema':'Falta configurar una clave de OpenAI';
}}catch(e){{console.error(e)}}}}
async function tx(){{try{{await json('/api/transactions',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{kind:$('kind').value,amount:$('amount').value,note:$('note').value}})}});$('amount').value='';$('note').value='';await load()}}catch(e){{alert(e.message)}}}}
async function opp(){{try{{await json('/api/opportunities',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{name:$('oname').value,platform:$('platform').value,status:$('ostatus').value,expected_usd:$('expected').value,note:$('onote').value,source_url:$('source_url').value}})}});['oname','platform','expected','onote','source_url'].forEach(x=>$(x).value='');await load()}}catch(e){{alert(e.message)}}}}
async function saveKey(){{const key=$('apiKey').value.trim();if(!key){{alert('Pegá una clave para guardar.');return}}try{{await json('/api/settings',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{api_key:key}})}});$('apiKey').value='';alert('Clave guardada de forma segura.');await load()}}catch(e){{alert(e.message)}}}}
async function removeKey(){{try{{await json('/api/settings',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{api_key:''}})}});await load()}}catch(e){{alert(e.message)}}}}
async function runMission(){{const out=$('out');out.className='status';out.textContent='Creando investigación...';try{{const d=await json('/api/mission',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{mission:$('mission').value}})}});out.textContent='Investigando en la web...';let tries=0;const timer=setInterval(async()=>{{tries++;try{{const q=await json('/api/jobs/'+d.job_id);if(q.status==='success'){{clearInterval(timer);out.className='ok';out.textContent=q.result;await load()}}else if(q.status==='error'){{clearInterval(timer);out.className='err';out.textContent='La investigación terminó con un error controlado.\n'+(q.error||'');await load()}}else if(tries>900){{clearInterval(timer);out.className='err';out.textContent='La investigación sigue en curso. Podés cerrar el navegador; el trabajo queda guardado. ';await load()}}}}catch(e){{}}}},1000)}}catch(e){{out.className='err';out.textContent=e.message}}}}
load();
</script>
""")


@app.get('/health')
async def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@app.get('/login', response_class=HTMLResponse)
async def login() -> str:
    return SETUP_PAGE if not has_user() else LOGIN_PAGE


@app.post('/setup', response_class=HTMLResponse)
async def setup(username: str = Form(...), password: str = Form(...), password2: str = Form(...)):
    if has_user():
        return RedirectResponse('/login', 303)
    if password != password2:
        return HTMLResponse(page("<div class='wrap'><div class='card'><h2>Las contraseñas no coinciden.</h2><a href='/login'>Volver</a></div></div>"), 400)
    try:
        create_user(username, hash_password(password))
    except Exception as exc:
        return HTMLResponse(page(f"<div class='wrap'><div class='card'><h2>Error de configuración</h2><p>{html.escape(str(exc))}</p><a href='/login'>Volver</a></div></div>"), 400)
    return RedirectResponse('/login', 303)


@app.post('/login')
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_user(username)
    if user and verify_password(user["password_hash"], password):
        request.session["user"] = user["username"]
        return RedirectResponse('/', 303)
    return HTMLResponse(page("<div class='wrap'><div class='card'><h2>Usuario o contraseña incorrectos.</h2><a href='/login'>Volver</a></div></div>"), 401)


@app.post('/logout')
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', 303)


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    if not authorized(request):
        return RedirectResponse('/login', 303)
    return dashboard()


@app.get('/api/metrics')
async def api_metrics(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    return metrics()


@app.get('/api/transactions')
async def api_transactions(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    return {"transactions": list_transactions()}


@app.post('/api/transactions')
async def api_add_transaction(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    try:
        data = await request.json()
        add_transaction(data.get('kind'), data.get('amount'), data.get('note',''))
        return {"ok": True}
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get('/api/opportunities')
async def api_opportunities(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    return {"opportunities": list_opportunities()}


@app.post('/api/opportunities')
async def api_add_opportunity(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    try:
        data = await request.json()
        add_opportunity(data.get('name',''), data.get('platform',''), data.get('status','investigar'), data.get('expected_usd',0), data.get('note',''), data.get('source_url',''))
        return {"ok": True}
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get('/api/runs')
async def api_runs(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    return {"runs": list_runs()}


@app.get('/api/settings')
async def api_settings(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    return {"configured": bool(get_openai_api_key())}


@app.post('/api/settings')
async def api_settings_save(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    try:
        data = await request.json()
        key = (data.get('api_key') or '').strip()
        set_openai_api_key(key)
        return {"ok": True, "configured": bool(get_openai_api_key())}
    except Exception as exc:
        return JSONResponse({"detail": f"No se pudo guardar la configuración: {exc}"}, status_code=400)


@app.post('/api/mission')
async def api_mission(request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    try:
        data = await request.json()
        mission = (data.get('mission') or DEFAULT_MISSION).strip()
        if not mission:
            raise ValueError('La misión está vacía.')
        job_id = create_job(mission)
        EXECUTOR.submit(execute_job, job_id, mission)
        return {"job_id": job_id, "status": "queued"}
    except Exception as exc:
        logger.exception("No se pudo crear la misión")
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get('/api/jobs/{job_id}')
async def api_job(job_id: int, request: Request):
    if not authorized(request): return JSONResponse({"detail": "No autorizado"}, status_code=401)
    job = get_job(job_id)
    if not job: return JSONResponse({"detail": "Trabajo inexistente"}, status_code=404)
    return job
