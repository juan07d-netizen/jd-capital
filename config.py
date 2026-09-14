import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
DATABASE_URL = os.getenv("DATABASE_URL", "")
AUTO_SPEND_USD = float(os.getenv("JD_AUTO_SPEND_USD", "0"))
ROOT = Path(__file__).resolve().parent
OBJECTIVE = """
JD Capital is Juan's private wealth-building system.
Maximize long-term net worth through legitimate, scalable and increasingly
automated opportunities while preserving capital.
Separate fact, estimate and hypothesis. Verify current platform rules and Argentina
eligibility. Do not invent earnings. Do not commit fraud, spam, impersonation,
unauthorized access, tax evasion, debt or high-impact financial operations.
Automatic spending is disabled by default.
"""
MISSION = """
Find and verify current legitimate opportunities to generate the first USD with
zero initial capital. Prioritize Argentina, then global opportunities. Include
microtasks, user testing, affiliate/lead generation, digital products, marketplaces,
AI automation, micro-SaaS, e-commerce and agent economy. Verify current rules,
payment mechanics and demand. Rank candidates and design the cheapest validation
experiment for each.
"""
