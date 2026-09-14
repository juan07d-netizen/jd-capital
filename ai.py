import os
from openai import OpenAI
from config import MODEL, OBJECTIVE

class AIConfigError(RuntimeError):
    pass

def run_research(mission: str) -> str:
    key=os.getenv("OPENAI_API_KEY")
    if not key:
        raise AIConfigError("Falta OPENAI_API_KEY en Railway.")
    client=OpenAI(api_key=key)
    response=client.responses.create(
        model=MODEL,
        tools=[{"type":"web_search"}],
        input=OBJECTIVE+"\n\nMISIÓN:\n"+mission+"\n\nUsá búsqueda web. Citá las fuentes con sus URLs. Priorizá datos actuales y separá hechos de estimaciones."
    )
    return response.output_text
