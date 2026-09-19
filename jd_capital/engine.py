from __future__ import annotations

import threading

from .ai import poll_research, start_research
from .db import get_job, save_run, update_job

_lock = threading.Lock()


def execute_job(job_id: int, mission: str) -> None:
    # Local release: serialize provider calls to avoid accidental rate-limit storms.
    with _lock:
        try:
            update_job(job_id, "running")
            _, response_id = start_research(mission)
            # Persist the provider id immediately so a process restart can recover the job.
            update_job(job_id, "running", provider_response_id=response_id)
            result = poll_research(response_id)
            save_run(mission, result, "success", job_id)
            update_job(job_id, "success", result=result, provider_response_id=response_id)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            save_run(mission, message, "error", job_id)
            update_job(job_id, "error", error=message)


def resume_job(job_id: int) -> None:
    job = get_job(job_id)
    if not job:
        return
    response_id = job.get("provider_response_id")
    if not response_id:
        update_job(job_id, "error", error="Investigación interrumpida antes de obtener el identificador del proveedor.")
        save_run(job["mission"], "Investigación interrumpida antes de obtener el identificador del proveedor.", "error", job_id)
        return
    with _lock:
        try:
            update_job(job_id, "running")
            result = poll_research(response_id)
            save_run(job["mission"], result, "success", job_id)
            update_job(job_id, "success", result=result, provider_response_id=response_id)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            save_run(job["mission"], message, "error", job_id)
            update_job(job_id, "error", error=message, provider_response_id=response_id)
