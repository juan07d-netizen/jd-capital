import os
from dotenv import load_dotenv
load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
DATABASE_URL = os.getenv("DATABASE_URL", "")
AUTO_SPEND_USD = float(os.getenv("JD_AUTO_SPEND_USD", "0"))
OBJECTIVE = """
JD Capital is Juan's private wealth-building intelligence system. Find legitimate,
scalable ways to build income and net worth. Verify current rules, eligibility,
payment mechanics and demand. Never invent earnings. Do not recommend fraud,
spam, impersonation, unauthorized access, tax evasion, debt, gambling or high-risk
financial actions. Automatic spending is disabled by default.
"""
DEFAULT_MISSION = """
Find and verify the best current opportunities to earn the first USD with zero
starting capital. Prioritize Argentina, then global options. Consider microtasks,
user testing, lead generation, affiliate opportunities, digital products,
AI automation, micro-SaaS, marketplaces and other legitimate online income.
Return a ranked table with: opportunity, why it fits, current availability,
Argentina eligibility, payout method, realistic earning range, time to first
payout, risks, verification sources, and the cheapest validation step.
"""
