from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from ResearchAgent import research_agent

def coerce_to_text(content) -> str:
    """Coerce LangChain/OpenAI message content into a plain string for A2A."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    # OpenAI Responses-style: [{"type":"text","text":"..."}, ...]
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text")
                if isinstance(t, str) and t.strip():
                    texts.append(t)
        # fallback: stringify if no text parts found
        return "\n".join(texts) if texts else str(content)

    if isinstance(content, dict):
        t = content.get("text")
        return t if isinstance(t, str) else str(content)

    return str(content)

class ResearchAgentExecutor(AgentExecutor):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.agent = research_agent

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
        print("research agent:")
        print("query:", query)
        print("response:", last_msg)
        content = last_msg.content if hasattr(last_msg, "content") else last_msg.get("content", str(last_msg))
        reply_text = coerce_to_text(content)

        await event_queue.enqueue_event(new_agent_text_message(reply_text))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')
