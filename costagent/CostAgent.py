from langchain_openai import ChatOpenAI

from langchain.agents import create_agent
from langchain_core.tools import tool
from dotenv import load_dotenv
from typing import Any, Dict, Optional

load_dotenv()

@tool
def estimate_trip_cost(
    destination: str,
    days: int,
    travelers: int,
    comfort: str = "mid",
) -> Dict[str, Any]:
    """
    Estimate a rough trip budget (SGD) using simple heuristics.
    comfort: budget | mid | premium
    Returns a breakdown and total estimate in SGD.
    """
    if days <= 0 or travelers <= 0:
        raise ValueError("days and travelers must be > 0")

    comfort = comfort.lower().strip()
    if comfort not in {"budget", "mid", "premium"}:
        raise ValueError("comfort must be one of: budget, mid, premium")

    # Very rough per-person-per-day estimates (SGD) excluding flights
    lodging_per_person_per_day = {"budget": 60, "mid": 140, "premium": 300}[comfort]
    food_per_person_per_day = {"budget": 30, "mid": 60, "premium": 120}[comfort]
    local_transport_per_person_per_day = {"budget": 10, "mid": 20, "premium": 50}[comfort]
    activities_per_person_per_day = {"budget": 20, "mid": 50, "premium": 120}[comfort]

    lodging = lodging_per_person_per_day * travelers * days
    food = food_per_person_per_day * travelers * days
    transport = local_transport_per_person_per_day * travelers * days
    activities = activities_per_person_per_day * travelers * days

    subtotal = lodging + food + transport + activities
    contingency = round(subtotal * 0.12)  # 12% buffer
    total = subtotal + contingency

    return {
        "destination": destination,
        "days": days,
        "travelers": travelers,
        "comfort": comfort,
        "currency": "SGD",
        "breakdown": {
            "lodging": lodging,
            "food": food,
            "local_transport": transport,
            "activities": activities,
            "contingency": contingency,
        },
        "total_estimate": total,
        "note": "Heuristic estimate excludes international flights/insurance/visa fees.",
    }

COST_SYSTEM = """You are CostAgent.
Your ONLY job: compute total cost.
Rules:
- Never invent numbers, use tools avaiable.
- If destination/days/travelers/comfort are missing, ask for them (max 2 questions) and stop.
- If user says 'add an additional one-day trip', treat it as +1 day ONLY IF baseline days is known.
- Return: total cost + short assumptions.
"""

cost_agent = create_agent(
    model=ChatOpenAI(model="gpt-4.1-mini", temperature=0.1),
    tools=[estimate_trip_cost],
    system_prompt=COST_SYSTEM,
    name="cost_agent",
)