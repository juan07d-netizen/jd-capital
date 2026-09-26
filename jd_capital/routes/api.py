from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import APP_NAME, APP_VERSION, DEFAULT_MISSION
from ..credentials import get_openai_api_key, set_openai_api_key
from ..db import create_job, get_job, list_runs
from ..services.current_finance import current_metrics, current_transactions, record_transaction
from ..services.opportunities import create_opportunity, current_opportunities
from ..services.research import submit_research
from .dependencies import authorized

logger = logging.getLogger(APP_NAME)
router = APIRouter()


def _unauthorized() -> JSONResponse:
    return JSONResponse({"detail": "No autorizado"}, status_code=401)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@router.get("/api/metrics")
async def api_metrics(request: Request):
    return _unauthorized() if not authorized(request) else current_metrics()


@router.get("/api/transactions")
async def api_transactions(request: Request):
    return _unauthorized() if not authorized(request) else {"transactions": current_transactions()}


@router.post("/api/transactions")
async def api_add_transaction(request: Request):
    if not authorized(request):
        return _unauthorized()
    try:
        data = await request.json()
        key = (request.headers.get("idempotency-key") or data.get("idempotency_key") or "").strip()
        record_transaction(data.get("kind"), data.get("amount"), data.get("note", ""), key or None)
        return {"ok": True}
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@router.get("/api/opportunities")
async def api_opportunities(request: Request):
    return _unauthorized() if not authorized(request) else {"opportunities": current_opportunities()}


@router.post("/api/opportunities")
async def api_add_opportunity(request: Request):
    if not authorized(request):
        return _unauthorized()
    try:
        data = await request.json()
        create_opportunity(data)
        return {"ok": True}
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@router.get("/api/runs")
async def api_runs(request: Request):
    return _unauthorized() if not authorized(request) else {"runs": list_runs()}


@router.get("/api/settings")
async def api_settings(request: Request):
    return _unauthorized() if not authorized(request) else {"configured": bool(get_openai_api_key())}


@router.post("/api/settings")
async def api_settings_save(request: Request):
    if not authorized(request):
        return _unauthorized()
    try:
        data = await request.json()
        set_openai_api_key((data.get("api_key") or "").strip())
        return {"ok": True, "configured": bool(get_openai_api_key())}
    except Exception as exc:
        return JSONResponse({"detail": f"No se pudo guardar la configuración: {exc}"}, status_code=400)


@router.post("/api/mission")
async def api_mission(request: Request):
    if not authorized(request):
        return _unauthorized()
    try:
        data = await request.json()
        mission = (data.get("mission") or DEFAULT_MISSION).strip()
        if not mission:
            raise ValueError("La misión está vacía.")
        job_id = create_job(mission)
        submit_research(job_id, mission)
        return {"job_id": job_id, "status": "queued"}
    except Exception as exc:
        logger.exception("No se pudo crear la misión")
        return JSONResponse({"detail": str(exc)}, status_code=400)


@router.get("/api/jobs/{job_id}")
async def api_job(job_id: int, request: Request):
    if not authorized(request):
        return _unauthorized()
    job = get_job(job_id)
    return job if job else JSONResponse({"detail": "Trabajo inexistente"}, status_code=404)
