import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import (
    ItineraryAgentExecutor,  # type: ignore[import-untyped]
)


if __name__ == '__main__':
    # --8<-- [start:AgentSkill]
    skill = AgentSkill(
        id='itinerary_agent',
        name='Returns trip itinerary',
        description='produce the final itinerary and incorporate research notes + cost breakdown.',
        tags=['Returns trip itinerary'],
        examples=['Compose the final answer using the provided trip_spec, research_notes, and cost_breakdown for a 2-day Tokyo trip for 2 travelers with mid comfort focusing on food and anime.',
                  '''1) Day-by-day plan:
Day 1: Akihabara Exploration
- Visit various anime shops and electronics stores around Akihabara Station (5-minute walk).  
- Have lunch or a snack at Maidreamin Café to experience the maid-themed dining atmosphere with performances (reservation recommended).  
- Leisurely explore more themed cafés and shops in Akihabara at a relaxed pace.

Day 2: Harajuku and Kanda Myojin Shrine  
- Start the day at Harajuku, exploring Takeshita Street’s trendy shops and street food (5-minute walk from Harajuku Station).  
- Visit one or two animal cafés nearby for a unique and relaxing experience (reservation recommended).  
- Walk to Kanda Myojin Shrine (about 15 minutes from Akihabara) to enjoy a cultural and peaceful retreat popular among anime fans.

2) Total cost (SGD) + assumptions:  
Total estimated cost: SGD 1,210  
This includes lodging, food, local transport, activities, and contingency for 2 travelers over 2 days at mid comfort level. International flights, insurance, and visa fees are excluded.'''
    ])
    # [end:AgentSkill]

    # [start:AgentCard]
    # This will be the public-facing agent card
    public_agent_card = AgentCard(
        name='Itinerary Agent',
        description='Itinerary Agent',
        url='http://localhost:9998/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],  # Only the basic skill for the public card
        supports_authenticated_extended_card=True,
    )
    # [end:AgentCard]

    request_handler = DefaultRequestHandler(
        agent_executor=ItineraryAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler
    )

    uvicorn.run(server.build(), host='0.0.0.0', port=9998)
