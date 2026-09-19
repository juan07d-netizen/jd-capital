from __future__ import annotations

import os
import time
from typing import Any, Callable

from .config import (
    MAX_MISSION_CHARS,
    MAX_OUTPUT_TOKENS,
    MODEL,
    POLL_INTERVAL_SECONDS,
    RESEARCH_TIMEOUT_SECONDS,
)
from .credentials import get_openai_api_key


class AIConfigError(RuntimeError):
    pass


class AIRateLimitError(RuntimeError):
    pass


class AIUnavailableError(RuntimeError):
    pass


ClientFactory = Callable[[str], Any]


def _client(factory: ClientFactory | None = None):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIUnavailableError("Falta la dependencia openai.") from exc
    key = get_openai_api_key()
    if not key:
        raise AIConfigError("JD Capital todavía no tiene configurada la clave de OpenAI.")
    maker = factory or OpenAI
    return maker(api_key=key, timeout=60.0, max_retries=0)


def _prompt(mission: str) -> str:
    mission = (mission or "").strip()
    if not mission:
        raise ValueError("La misión está vacía.")
    if len(mission) > MAX_MISSION_CHARS:
        mission = mission[:MAX_MISSION_CHARS] + "\n[misión recortada por límite de tamaño]"
    return f"""You are the research engine for JD Capital.

OBJECTIVE:
Find legitimate, scalable ways to build income and net worth. Verify current rules,
eligibility, payment mechanics, demand, and risks. Never invent earnings. Do not
recommend fraud, spam, impersonation, unauthorized access, tax evasion, debt,
gambling, or unauthorized financial activity. For human-work platforms,
distinguish AI assistance from actions that must remain human. Never recommend
fake accounts, location spoofing, bots, scripts, scraping, or automation that
violates platform rules. Automatic spending is disabled.

MISSION:
{mission}

RESEARCH RULES:
- You MUST use live web search and cite sources.
- Prioritize official/primary sources, then reputable secondary sources.
- Prefer current information and explicitly state dates when relevant.
- For Argentina, verify eligibility, payment method, withdrawal threshold, identity requirements, and platform restrictions.
- For automation, classify: allowed; human-in-the-loop/assistance; prohibited or unclear.
- Separate verified facts from estimates and clearly label uncertainty.
- Do not promise earnings or investment returns.
- End with the cheapest legitimate human validation step.
"""


def start_research(mission: str) -> tuple[str, str]:
    client = _client()
    prompt = _prompt(mission)
    try:
        resp = client.responses.create(
            model=MODEL,
            input=prompt,
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": "medium",
                    "user_location": {
                        "type": "approximate",
                        "country": "AR",
                    },
                    "external_web_access": True,
                }
            ],
            tool_choice="required",
            max_output_tokens=MAX_OUTPUT_TOKENS,
            background=True,
            store=True,
        )
    except Exception as exc:
        code = getattr(exc, "status_code", None)
        if code == 429:
            raise AIRateLimitError("La API está temporalmente limitada. Esperá y reintentá.") from exc
        if isinstance(code, int) and code >= 500:
            raise AIUnavailableError("El servicio de IA no está disponible en este momento.") from exc
        raise
    response_id = getattr(resp, "id", None)
    if not response_id:
        raise AIUnavailableError("La API no devolvió un identificador de investigación.")
    return getattr(resp, "status", "queued"), response_id


def poll_research(response_id: str) -> str:
    client = _client()
    started = time.monotonic()
    while True:
        if time.monotonic() - started > RESEARCH_TIMEOUT_SECONDS:
            raise TimeoutError("La investigación superó el tiempo máximo configurado.")
        try:
            resp = client.responses.retrieve(response_id)
        except Exception as exc:
            code = getattr(exc, "status_code", None)
            if code == 429:
                time.sleep(min(15.0, max(2.0, POLL_INTERVAL_SECONDS * 3)))
                continue
            if isinstance(code, int) and code >= 500:
                time.sleep(min(15.0, max(2.0, POLL_INTERVAL_SECONDS * 2)))
                continue
            raise
        status = getattr(resp, "status", None)
        if status in ("queued", "in_progress"):
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if status == "completed":
            text = getattr(resp, "output_text", None)
            if text:
                return text
            raise AIUnavailableError("La investigación terminó sin devolver texto.")
        err = getattr(resp, "error", None)
        detail = getattr(err, "message", None) if err else None
        raise AIUnavailableError(detail or f"Estado final inesperado: {status}")


def run_research(mission: str) -> tuple[str, str]:
    _, response_id = start_research(mission)
    return poll_research(response_id), response_id
