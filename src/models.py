"""Core typed contracts for the Investor Copilot API service."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    FINANCIAL_CALCULATOR = "financial_calculator"
    FINANCIAL_PLANNING = "financial_planning"
    GENERAL_QUERY = "general_query"
    INVESTMENT_STRATEGY = "investment_strategy"
    MARKET_RESEARCH = "market_research"
    PORTFOLIO_HEALTH = "portfolio_health"
    PREDICTIVE_ANALYSIS = "predictive_analysis"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    RISK_ASSESSMENT = "risk_assessment"


class SafetyCategory(str, Enum):
    FRAUD = "fraud"
    GENERAL_EDUCATION = "general_education"
    GUARANTEED_RETURNS = "guaranteed_returns"
    INSIDER_TRADING = "insider_trading"
    MARKET_MANIPULATION = "market_manipulation"
    MONEY_LAUNDERING = "money_laundering"
    RECKLESS_ADVICE = "reckless_advice"
    SANCTIONS_EVASION = "sanctions_evasion"


class QueryRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)


class SafetyVerdict(BaseModel):
    blocked: bool
    category: SafetyCategory | None = None
    message: str | None = None


class InformationalSafetyVerdict(BaseModel):
    safe: bool = True
    category: str | None = None
    rationale: str | None = None


class ClassifierEntities(BaseModel):
    action: str | None = None
    amount: float | None = None
    currency: str | None = None
    frequency: str | None = None
    goal: str | None = None
    horizon: str | None = None
    index: str | None = None
    intent: str | None = None
    period_years: int | None = None
    rate: float | None = None
    sectors: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    time_period: str | None = None
    topics: list[str] = Field(default_factory=list)


class ClassificationResult(BaseModel):
    intent: str
    agent: AgentName
    entities: ClassifierEntities = Field(default_factory=ClassifierEntities)
    informational_safety_verdict: InformationalSafetyVerdict = Field(
        default_factory=InformationalSafetyVerdict
    )
    used_fallback: bool = False


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class PositionPerformance(BaseModel):
    ticker: str
    return_pct: float | None = None
    market_value: float | None = None
    warning: str | None = None


class ConcentrationRisk(BaseModel):
    top_position_pct: float | None = None
    top_3_positions_pct: float | None = None
    flag: Literal["low", "moderate", "warning", "high"]


class PerformanceSummary(BaseModel):
    total_return_pct: float | None = None
    annualized_return_pct: float | None = None


class BenchmarkComparison(BaseModel):
    benchmark: str
    portfolio_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    alpha_pct: float | None = None
    warning: str | None = None


class Observation(BaseModel):
    severity: Literal["info", "warning", "high"]
    text: str


class NextAction(BaseModel):
    label: str
    rationale: str


class PortfolioHealthResponse(BaseModel):
    concentration_risk: ConcentrationRisk
    performance: PerformanceSummary
    benchmark_comparison: BenchmarkComparison | None = None
    observations: list[Observation] = Field(default_factory=list)
    next_action: NextAction
    disclaimer: str
    position_performance: list[PositionPerformance] = Field(default_factory=list)


class StubAgentResponse(BaseModel):
    classified_intent: str
    extracted_entities: ClassifierEntities
    agent: AgentName
    message: str


class StreamEvent(BaseModel):
    event: Literal["meta", "thinking", "response", "error", "done"]
    data: dict[str, Any]
