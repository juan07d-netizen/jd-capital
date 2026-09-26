from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..db import stale_jobs
from ..engine import execute_job, resume_job

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jd-research")


def submit_research(job_id: int, mission: str) -> None:
    _executor.submit(execute_job, job_id, mission)


def recover_research_jobs() -> None:
    for job in stale_jobs():
        _executor.submit(resume_job, int(job["id"]))


def shutdown_research() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)
