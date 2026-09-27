from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from CostAgent import cost_agent

class CostAgentExecutor(AgentExecutor):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.agent = cost_agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        result = await self.agent.ainvoke({
            "messages": [{"role": "user", "content": query}]
        })
        last_msg = result["messages"][-1]
        print("cost agent:")
        print("query:", query)
        print("response:", last_msg)
        reply_text = last_msg.content if hasattr(last_msg, "content") else last_msg.get("content", str(last_msg))
        await event_queue.enqueue_event(new_agent_text_message(reply_text))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')
