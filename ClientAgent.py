import asyncio
import json
import logging
import re
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import AgentCard, MessageSendParams, SendMessageRequest

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("client_agent")


AgentId = Literal[
    "research_agent",
    "cost_agent",
    "itinerary_agent",
]

AGENT_ENDPOINTS: Dict[str, str] = {
    "research_agent": "http://localhost:9996",
    "cost_agent": "http://localhost:9997",
    "itinerary_agent": "http://localhost:9998",
}


class ClientAgentApp:
    def __init__(self) -> None:
        # Cards are deliberately keyed by stable machine-readable IDs, not by
        # display names such as "Research Agent".
        self.cards: Dict[str, AgentCard] = {}
        self.agents: str = ""

    # -----------------------------
    # Agent discovery
    # -----------------------------
    async def discover_agents(self) -> None:
        async with httpx.AsyncClient(timeout=30.0) as httpx_client:
            for agent_id, base_url in AGENT_ENDPOINTS.items():
                try:
                    resolver = A2ACardResolver(
                        httpx_client=httpx_client,
                        base_url=base_url,
                    )
                    card = await resolver.get_agent_card()
                    self.cards[agent_id] = card
                    logger.info(
                        "Discovered agent: id=%s, name=%s",
                        agent_id,
                        card.name,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to discover agent id=%s at %s: %s",
                        agent_id,
                        base_url,
                        exc,
                    )

        if not self.cards:
            raise RuntimeError(
                "No remote agents were discovered. Start the A2A servers on "
                "ports 9996, 9997, and 9998 before running this client."
            )

        missing = sorted(set(AGENT_ENDPOINTS) - set(self.cards))
        if missing:
            logger.warning("Some agents were not discovered: %s", ", ".join(missing))

        self._build_agent_description()

    def _build_agent_description(self) -> None:
        """Build the system-prompt list using both agent ID and display name."""
        lines = []
        for agent_id, card in self.cards.items():
            lines.append(f"- {agent_id} ({card.name}): {card.description}")
        self.agents = "\n".join(lines)

    # -----------------------------
    # Agent ID resolution
    # -----------------------------
    @staticmethod
    def _normalise_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

    def _resolve_agent_id(self, requested_name: str) -> str:
        """
        Resolve either a stable ID (research_agent) or a display name
        (Research Agent) to the ID used in self.cards.
        """
        normalised = self._normalise_name(requested_name)

        if normalised in self.cards:
            return normalised

        for agent_id, card in self.cards.items():
            aliases = {
                self._normalise_name(agent_id),
                self._normalise_name(card.name),
            }

            # Skill IDs/names are also useful aliases if supplied by the model.
            for skill in getattr(card, "skills", []) or []:
                skill_id = getattr(skill, "id", None)
                skill_name = getattr(skill, "name", None)
                if skill_id:
                    aliases.add(self._normalise_name(skill_id))
                if skill_name:
                    aliases.add(self._normalise_name(skill_name))

            if normalised in aliases:
                return agent_id

        available = ", ".join(sorted(self.cards))
        raise ValueError(
            f"Unknown agent_name={requested_name!r}. "
            f"Use one of these IDs: {available}"
        )

    # -----------------------------
    # A2A response parsing
    # -----------------------------
    @staticmethod
    def _parts_to_text(parts: Any) -> str:
        """Extract text from common A2A v0.3 Part JSON shapes."""
        if not isinstance(parts, list):
            return ""

        texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue

            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
                continue

            # Some SDK versions wrap a concrete Part under "root".
            root = part.get("root")
            if isinstance(root, dict):
                root_text = root.get("text")
                if isinstance(root_text, str) and root_text.strip():
                    texts.append(root_text.strip())

        return "\n".join(texts)

    @classmethod
    def _extract_response_text(cls, data: Dict[str, Any]) -> str:
        """
        Handle both possible A2A v0.3 message/send results:
        - a direct Message with result.parts
        - a Task with artifacts, status.message, or history
        """
        result = data.get("result")
        if not isinstance(result, dict):
            return json.dumps(data, ensure_ascii=False)

        # 1. Direct Message response.
        direct_text = cls._parts_to_text(result.get("parts"))
        if direct_text:
            return direct_text

        # 2. Completed Task artifacts normally contain the useful final output.
        artifacts = result.get("artifacts")
        if isinstance(artifacts, list):
            artifact_texts = [
                cls._parts_to_text(artifact.get("parts"))
                for artifact in artifacts
                if isinstance(artifact, dict)
            ]
            artifact_text = "\n".join(text for text in artifact_texts if text)
            if artifact_text:
                return artifact_text

        # 3. Task status may carry the final agent message.
        status = result.get("status")
        if isinstance(status, dict):
            status_message = status.get("message")
            if isinstance(status_message, dict):
                status_text = cls._parts_to_text(status_message.get("parts"))
                if status_text:
                    return status_text

        # 4. Fall back to the newest agent message in task history.
        history = result.get("history")
        if isinstance(history, list):
            for message in reversed(history):
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role", "")).lower()
                if role in {"agent", "assistant", "role_agent"}:
                    history_text = cls._parts_to_text(message.get("parts"))
                    if history_text:
                        return history_text

        # Keep diagnostics visible rather than returning an empty string.
        return json.dumps(result, ensure_ascii=False)

    # -----------------------------
    # Tool used by the LangChain agent
    # -----------------------------
    async def ask_remote_agent(
        self,
        agent_name: AgentId,
        text: str,
    ) -> Dict[str, Any]:
        """
        Send a request to a remote A2A agent.

        Args:
            agent_name: Exact agent ID: research_agent, cost_agent, or
                itinerary_agent.
            text: Complete request to send to that remote agent.

        Returns:
            The resolved agent ID, display name, and response text.
        """
        agent_id = self._resolve_agent_id(agent_name)
        card = self.cards[agent_id]

        # Create the A2A client with the same live HTTP client used for this
        # call. Do not cache it across `async with` blocks because that would
        # leave it holding a closed httpx client on a later tool call.
        async with httpx.AsyncClient(timeout=60.0) as httpx_client:
            client = A2AClient(httpx_client=httpx_client, agent_card=card)

            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message={
                        "role": "user",
                        "parts": [{"type": "text", "text": text}],
                        "messageId": uuid4().hex,
                    }
                ),
            )

            response = await client.send_message(request)
            data = response.model_dump(mode="json", exclude_none=True)

        response_text = self._extract_response_text(data)
        logger.info("Received response from %s", agent_id)

        return {
            "agent_id": agent_id,
            "agent_name": card.name,
            "response_text": response_text,
            "number": self._extract_number(response_text),
        }

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        # Prefer a currency amount so that "2-day" is not mistaken for cost.
        currency_match = re.search(
            r"(?:SGD|S\$)\s*([\d,]+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE,
        )
        if currency_match:
            return float(currency_match.group(1).replace(",", ""))

        number_match = re.search(r"(-?\d+(?:\.\d+)?)", text)
        return float(number_match.group(1)) if number_match else None

    # -----------------------------
    # Build the client-side orchestrator
    # -----------------------------
    def build_llm_agent(self):
        system_prompt = f"""
You are a client-side travel orchestration agent.

Available remote agents:
{self.agents}

IMPORTANT: agent_name must be one of these exact IDs:
- research_agent
- cost_agent
- itinerary_agent

For every complete travel-planning request, follow this workflow:
1. Call research_agent with the full trip requirements.
2. Call cost_agent with the full trip requirements.
3. After both responses are available, call itinerary_agent. Include in its
   request the original trip requirements, the research response, and the cost
   response so it can compose the final answer.
4. Return the final itinerary_agent response to the user.

Rules:
- Ask a clarifying question only when essential information is missing.
- Do not invent research facts or cost figures.
- Do not call itinerary_agent before obtaining both research and cost results.
- Do not expose internal tool-call JSON in the final response.

Final output format:
1) Day-by-day plan
2) Total cost (SGD) and assumptions
"""

        return create_agent(
            model="openai:gpt-4o",
            tools=[self.ask_remote_agent],
            name="client_agent",
            system_prompt=system_prompt,
        )


async def main() -> None:
    app = ClientAgentApp()
    await app.discover_agents()

    agent = app.build_llm_agent()

    user_prompt = (
        "Plan a 2-day Tokyo trip for 2 adults, mid comfort. "
        "We like food and anime. Avoid packed schedules."
    )
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_prompt}]}
    )

    last_msg = result["messages"][-1]
    print(last_msg.content)


if __name__ == "__main__":
    asyncio.run(main())
