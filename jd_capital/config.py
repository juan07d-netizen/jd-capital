from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

APP_NAME = "JD Capital"
APP_VERSION = "2.1.0"

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv()

# The current OpenAI Responses API docs show the web_search tool on current GPT
# models. Keep the model configurable so the executable can be updated without
# rebuilding the application just to change a model name.
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
MAX_MISSION_CHARS = int(os.getenv("JD_MAX_MISSION_CHARS", "12000"))
MAX_OUTPUT_TOKENS = int(os.getenv("JD_MAX_OUTPUT_TOKENS", "5000"))
POLL_INTERVAL_SECONDS = float(os.getenv("JD_POLL_INTERVAL_SECONDS", "2.0"))
RESEARCH_TIMEOUT_SECONDS = int(os.getenv("JD_RESEARCH_TIMEOUT_SECONDS", "900"))
PORT = int(os.getenv("JD_PORT", "8000"))


def default_data_dir() -> Path:
    root = os.getenv("JD_DATA_DIR", "").strip()
    if root:
        return Path(root).expanduser().resolve()
    if os.name == "nt":
        appdata = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "JD Capital"
    return Path.home() / ".jd_capital"


# Compatibility constants; runtime code should prefer get_data_dir()/get_db_file()
# so tests and first-run setup can change JD_DATA_DIR safely.
DATA_DIR = default_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DATA_DIR / "jd_capital.sqlite3"
ENV_FILE = BASE_DIR.parent / ".env"


def get_data_dir() -> Path:
    path = default_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_file() -> Path:
    return get_data_dir() / "jd_capital.sqlite3"


DEFAULT_MISSION = """
Investigá oportunidades actuales y legítimas para generar los primeros USD de JD Capital con poco o cero capital inicial, priorizando participantes de Argentina y luego opciones globales. Incluí: entrenamiento/evaluación de IA, microtareas, encuestas, user testing, testing de productos, servicios digitales asistidos por IA, generación de leads, afiliación y productos digitales. Para cada opción verificá con fuentes actuales: elegibilidad para Argentina, disponibilidad, forma y umbral de pago, tiempo estimado hasta el primer cobro, requisitos de identidad/ubicación, reglas sobre automatización, riesgos y el paso humano más barato para validar la oportunidad. No inventes ingresos; distinguí hechos verificados de estimaciones. Priorizá fuentes oficiales.
""".strip()

OBJECTIVE = """
JD Capital is Juan's private wealth-building intelligence system. Find legitimate,
scalable ways to build income and net worth. Verify current rules, eligibility,
payment mechanics and demand. Never invent earnings. Do not recommend fraud,
spam, impersonation, unauthorized access, tax evasion, debt, gambling or
unauthorized financial activity. For human-work platforms, distinguish AI
assistance from actions that must remain human. Never recommend fake accounts,
location spoofing, bots, scripts, scraping or automation that violates platform
rules. Automatic spending is disabled by design.
""".strip()
