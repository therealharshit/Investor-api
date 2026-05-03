"""LLM-backed intent classification with deterministic fallback."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.models import (
    AgentName,
    ClassificationResult,
    ClassifierEntities,
    ConversationTurn,
    InformationalSafetyVerdict,
)


def _fallback_classification(query: str) -> ClassificationResult:
    return ClassificationResult(
        intent="classification_fallback",
        agent=AgentName.GENERAL_QUERY,
        entities=ClassifierEntities(),
        informational_safety_verdict=InformationalSafetyVerdict(
            safe=True,
            rationale=f"Classifier fallback used for query: {query[:120]}",
        ),
        used_fallback=True,
    )


def classify(
    query: str,
    history: list[ConversationTurn],
    llm: Any,
) -> ClassificationResult:
    """Classify the current user query plus bounded prior context."""

    del history  # Used later when prompt construction lands.

    try:
        raw = llm(query)
    except Exception:
        return _fallback_classification(query)

    try:
        return ClassificationResult.model_validate(raw)
    except ValidationError:
        return _fallback_classification(query)
