from langchain_openai import ChatOpenAI

from langchain.agents import create_agent

from dotenv import load_dotenv
load_dotenv()

ITINERARY_SYSTEM = """You are ItineraryAgent.
Your job: produce the final itinerary and incorporate research notes + cost breakdown.
Rules:
- Do NOT invent numeric costs; only use cost_breakdown if present.
- If cost_breakdown missing, ask for required info (max 2 questions).
Output format:
1) Day-by-day plan (brief)
2) Total cost (SGD) + assumptions
"""

itinerary_agent = create_agent(
    model=ChatOpenAI(model="gpt-4.1-mini", temperature=0.4),
    tools=[],
    system_prompt=ITINERARY_SYSTEM,
    name="itinerary_agent",
)