from ai import run_research
from db import save_run

def run_mission(mission):
    try:
        result=run_research(mission)
        save_run(mission,result,"success")
        return result
    except Exception as exc:
        save_run(mission,str(exc),"error")
        raise
