import asyncio
from db import init_db
from engine import default_mission, run_mission_once
if __name__ == "__main__":
    init_db()
    asyncio.run(run_mission_once(default_mission(), source="cloud-cron"))
