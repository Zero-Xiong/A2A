from langchain_openai import ChatOpenAI

from langchain.agents import create_agent

from dotenv import load_dotenv
load_dotenv()

RESEARCH_SYSTEM = """You are ResearchAgent.
Your ONLY job: gather factual, practical travel itinerary (not including cost) using web search.
Rules:
- Use web search when needed.
- Do NOT estimate or compute cost.
- Output ONLY 5 bullets max.
- Each bullet: destination + why + travel time + one practical note.
"""

research_agent = create_agent(
    model=ChatOpenAI(model="gpt-4.1-mini", temperature=0.2),
    tools=[{"type": "web_search_preview"}],
    system_prompt=RESEARCH_SYSTEM,
    name="research_agent",
)