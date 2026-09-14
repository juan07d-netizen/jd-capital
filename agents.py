import os
from agents import Agent, Runner, WebSearchTool, set_default_openai_key
from .config import OBJECTIVE, MODEL

key=os.getenv("OPENAI_API_KEY")
if key:
    set_default_openai_key(key, use_for_tracing=False)

def build():
    web=WebSearchTool()
    scout=Agent(name="JD Scout", model=MODEL, instructions=OBJECTIVE+"\nFind current opportunities and source URLs.", tools=[web])
    researcher=Agent(name="JD Researcher", model=MODEL, instructions=OBJECTIVE+"\nVerify existence, current rules, Argentina eligibility, payout mechanics and demand.", tools=[web])
    cfo=Agent(name="JD CFO", model=MODEL, instructions=OBJECTIVE+"\nEvaluate capital, unit economics, automation, scalability and risk. Never confuse revenue with profit.", tools=[web])
    validator=Agent(name="JD Validator", model=MODEL, instructions=OBJECTIVE+"\nDesign the cheapest legal experiment that can prove first revenue.", tools=[web])
    portfolio=Agent(name="JD Portfolio Manager", model=MODEL, instructions=OBJECTIVE+"\nRank a diversified set of opportunities instead of chasing one idea.", tools=[web])
    director=Agent(name="JD Director", model=MODEL, instructions=OBJECTIVE+"\nSynthesize all findings into a ranked action plan.", tools=[web])
    return scout,researcher,cfo,validator,portfolio,director

async def run_pipeline(mission):
    scout,researcher,cfo,validator,portfolio,director=build()
    a=(await Runner.run(scout, mission)).final_output
    b=(await Runner.run(researcher, "Verify these candidates:\n"+a)).final_output
    c=(await Runner.run(cfo, "Analyze economics and risk:\n"+b)).final_output
    d=(await Runner.run(validator, "Design minimum-cost experiments:\n"+c)).final_output
    e=(await Runner.run(portfolio, "Rank the portfolio using:\n"+c+"\nExperiments:\n"+d)).final_output
    f=(await Runner.run(director, "FINAL DECISION\nSCOUT:\n"+a+"\nRESEARCH:\n"+b+"\nCFO:\n"+c+"\nVALIDATOR:\n"+d+"\nPORTFOLIO:\n"+e)).final_output
    return f
