"""Agent routing."""

from __future__ import annotations

from src.agents.portfolio_health import run as run_portfolio_health
from src.models import AgentName, ClassificationResult, StubAgentResponse


def dispatch(classification: ClassificationResult, user: dict, market_data=None):
    if classification.agent == AgentName.PORTFOLIO_HEALTH:
        return run_portfolio_health(user, market_data=market_data)

    return StubAgentResponse(
        classified_intent=classification.intent,
        extracted_entities=classification.entities,
        agent=classification.agent,
        message=f"{classification.agent.value} is not implemented in this build.",
    )
