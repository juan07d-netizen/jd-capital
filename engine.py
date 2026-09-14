from .agents import run_pipeline
from .config import MISSION
from .db import add_opportunity, log_event

def default_mission():
    return MISSION

async def run_mission_once(mission, source="manual"):
    log_event("mission_started", source)
    try:
        report = await run_pipeline(mission)
        add_opportunity("Mission result","portfolio",0,0,0,"pending_review",report)
        log_event("mission_finished", source)
        return report
    except Exception as exc:
        log_event("mission_error", f"{type(exc).__name__}: {exc}")
        raise
