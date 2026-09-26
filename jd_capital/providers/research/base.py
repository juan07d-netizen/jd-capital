from __future__ import annotations

from typing import Protocol


class ResearchProvider(Protocol):
    """Provider boundary used by the current research job engine."""

    def start(self, mission: str) -> tuple[str, str]: ...

    def poll(self, provider_response_id: str) -> str: ...
