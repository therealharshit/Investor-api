"""Portfolio health agent contract.

Benchmark selection
-------------------
holdings markets
  -> dominant market?
     -> yes: market benchmark
     -> no: MSCI World fallback
"""

from __future__ import annotations

from src.models import (
    BenchmarkComparison,
    ConcentrationRisk,
    NextAction,
    Observation,
    PerformanceSummary,
    PortfolioHealthResponse,
)


DISCLAIMER = (
    "This is not investment advice. It is an informational portfolio summary "
    "based on the data available in this session."
)


def _build_empty_portfolio_response(user: dict) -> PortfolioHealthResponse:
    risk_profile = user.get("risk_profile", "your risk profile")
    return PortfolioHealthResponse(
        concentration_risk=ConcentrationRisk(flag="low"),
        performance=PerformanceSummary(),
        benchmark_comparison=None,
        observations=[
            Observation(
                severity="info",
                text=(
                    "You do not hold any positions yet, so the most useful first step "
                    "is building a simple diversified starting point."
                ),
            )
        ],
        next_action=NextAction(
            label="Start with a diversified core allocation",
            rationale=(
                f"Use your {risk_profile} profile to choose a small set of broad funds "
                "before considering single-stock ideas."
            ),
        ),
        disclaimer=DISCLAIMER,
    )


def run(user: dict, market_data=None, llm=None) -> PortfolioHealthResponse:
    """Temporary skeleton implementation for the hero agent."""

    del market_data, llm

    positions = user.get("positions", [])
    if not positions:
        return _build_empty_portfolio_response(user)

    return PortfolioHealthResponse(
        concentration_risk=ConcentrationRisk(flag="moderate"),
        performance=PerformanceSummary(),
        benchmark_comparison=BenchmarkComparison(benchmark="MSCI World"),
        observations=[
            Observation(
                severity="info",
                text="Portfolio health analysis scaffolded. Metric enrichment comes next.",
            )
        ],
        next_action=NextAction(
            label="Review your top position",
            rationale="The first live implementation step should prioritize concentration and benchmark context.",
        ),
        disclaimer=DISCLAIMER,
    )
