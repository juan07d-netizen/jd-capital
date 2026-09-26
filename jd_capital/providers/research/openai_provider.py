from __future__ import annotations

from ... import ai


class OpenAIResearchProvider:
    """Optional OpenAI adapter retained for backwards compatibility."""

    def start(self, mission: str) -> tuple[str, str]:
        return ai.start_research(mission)

    def poll(self, provider_response_id: str) -> str:
        return ai.poll_research(provider_response_id)
