from __future__ import annotations

import threading

from .ai import poll_research, start_research
from .db import get_job, save_run, update_job
from .providers.research.base import ResearchProvider

_lock = threading.Lock()


class _LegacyOpenAIProvider:
    """Compatibility adapter keeps existing monkeypatch-based regressions valid."""

    def start(self, mission: str) -> tuple[str, str]:
        return start_research(mission)

    def poll(self, provider_response_id: str) -> str:
        return poll_research(provider_response_id)


def execute_job(job_id: int, mission: str, provider: ResearchProvider | None = None) -> None:
    # Local release: serialize provider calls to avoid accidental rate-limit storms.
    with _lock:
        try:
            selected = provider or _LegacyOpenAIProvider()
            update_job(job_id, "running")
            _, response_id = selected.start(mission)
            # Persist the provider id immediately so a process restart can recover the job.
            update_job(job_id, "running", provider_response_id=response_id)
            result = selected.poll(response_id)
            save_run(mission, result, "success", job_id)
            update_job(job_id, "success", result=result, provider_response_id=response_id)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            save_run(mission, message, "error", job_id)
            update_job(job_id, "error", error=message)


def resume_job(job_id: int, provider: ResearchProvider | None = None) -> None:
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
            selected = provider or _LegacyOpenAIProvider()
            update_job(job_id, "running")
            result = selected.poll(response_id)
            save_run(job["mission"], result, "success", job_id)
            update_job(job_id, "success", result=result, provider_response_id=response_id)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            save_run(job["mission"], message, "error", job_id)
            update_job(job_id, "error", error=message, provider_response_id=response_id)
