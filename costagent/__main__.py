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
    CostAgentExecutor,  # type: ignore[import-untyped]
)


if __name__ == '__main__':
    # --8<-- [start:AgentSkill]
    skill = AgentSkill(
        id='cost_agent',
        name='Cost Agent',
        description='Returns trip estimated cost with cost breakdown',
        tags=['Returns trip estimated cost'],
        examples=['Estimate the cost and cost_breakdown for a 2-day Tokyo trip for 2 travelers with mid comfort.',
                  '''Total cost (SGD):  
Total estimated cost: SGD 1,210  
This includes lodging, food, local transport, activities, and contingency for 2 travelers over 2 days at mid comfort level. International flights, insurance, and visa fees are excluded.'''
    ])
    # [end:AgentSkill]

    # [start:AgentCard]
    # This will be the public-facing agent card
    public_agent_card = AgentCard(
        name='Cost Agent',
        description='Cost Agent',
        url='http://localhost:9997/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],  # Only the basic skill for the public card
        supports_authenticated_extended_card=True,
    )
    # [end:AgentCard]

    request_handler = DefaultRequestHandler(
        agent_executor=CostAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler
    )

    uvicorn.run(server.build(), host='0.0.0.0', port=9997)
