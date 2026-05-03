"""Portfolio health agent contract.

Benchmark selection
-------------------
holdings markets
  -> dominant market?
     -> yes: market benchmark
     -> no: MSCI World fallback
"""

from __future__ import annotations

from collections import Counter

from src.market_data import NullMarketDataAdapter
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

MARKET_BENCHMARKS = {
    "NASDAQ": "S&P 500",
    "NYSE": "S&P 500",
    "LSE": "FTSE 100",
    "EURONEXT_AMSTERDAM": "MSCI World",
    "TSE": "NIKKEI 225",
}


def _position_value(position: dict) -> float:
    return float(position.get("quantity", 0)) * float(position.get("avg_cost", 0))


def _build_concentration_risk(positions: list[dict]) -> ConcentrationRisk:
    values = sorted((_position_value(position) for position in positions), reverse=True)
    total = sum(values)
    top_position_pct = round(values[0] / total * 100, 1) if total else None
    top_3_positions_pct = round(sum(values[:3]) / total * 100, 1) if total else None

    flag = "low"
    if top_position_pct is not None:
        if top_position_pct >= 50:
            flag = "high"
        elif top_position_pct >= 30:
            flag = "warning"
        elif top_position_pct >= 20:
            flag = "moderate"

    return ConcentrationRisk(
        top_position_pct=top_position_pct,
        top_3_positions_pct=top_3_positions_pct,
        flag=flag,
    )


def _select_benchmark(user: dict, positions: list[dict]) -> str:
    weighted_exchanges = Counter()
    for position in positions:
        exchange = position.get("exchange")
        if exchange:
            weighted_exchanges[exchange] += _position_value(position)

    if not weighted_exchanges:
        return "S&P 500" if user.get("country") == "US" else "MSCI World"

    total_value = sum(weighted_exchanges.values())
    dominant_exchange, dominant_value = weighted_exchanges.most_common(1)[0]
    if total_value and dominant_value / total_value > 0.5:
        return MARKET_BENCHMARKS.get(dominant_exchange, "MSCI World")
    return "MSCI World"


def _build_observations(
    user: dict,
    positions: list[dict],
    concentration_risk: ConcentrationRisk,
    benchmark: str,
    quote_warnings: list[str],
    benchmark_warning: str | None,
) -> list[Observation]:
    observations: list[Observation] = []
    if concentration_risk.top_position_pct and concentration_risk.top_position_pct >= 50:
        largest = max(positions, key=_position_value)
        observations.append(
            Observation(
                severity="high",
                text=(
                    f"{largest['ticker']} makes up about {concentration_risk.top_position_pct:.1f}% "
                    "of your portfolio, which is very concentrated for a novice investor."
                ),
            )
        )
    elif concentration_risk.top_position_pct and concentration_risk.top_position_pct >= 30:
        largest = max(positions, key=_position_value)
        observations.append(
            Observation(
                severity="warning",
                text=(
                    f"{largest['ticker']} is your biggest holding at roughly "
                    f"{concentration_risk.top_position_pct:.1f}% of the portfolio."
                ),
            )
        )

    if user.get("risk_profile") == "conservative":
        observations.append(
            Observation(
                severity="info",
                text="Your holdings look more income and stability oriented than growth oriented, which fits a conservative profile.",
            )
        )
    else:
        observations.append(
            Observation(
                severity="info",
                text=f"I used {benchmark} as your comparison point because it best matches the markets your holdings are concentrated in.",
            )
        )

    if quote_warnings or benchmark_warning:
        observations.append(
            Observation(
                severity="warning",
                text="Some live market data was unavailable, so parts of this health check use degraded estimates rather than fresh prices.",
            )
        )

    return observations[:2]


def _build_next_action(
    positions: list[dict],
    concentration_risk: ConcentrationRisk,
) -> NextAction:
    if concentration_risk.top_position_pct and concentration_risk.top_position_pct >= 50:
        largest = max(positions, key=_position_value)
        return NextAction(
            label=f"Review whether {largest['ticker']} should stay this large",
            rationale=(
                "One holding now drives most of your outcome, so your next decision should be whether "
                "that concentration is intentional or needs trimming."
            ),
        )
    return NextAction(
        label="Review your top three positions together",
        rationale="Those holdings are most likely to drive your portfolio's behavior, so start there before making smaller tweaks.",
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
                    "You have no positions yet, so the most useful first step "
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
    """Portfolio health agent with graceful live-data degradation."""

    del llm

    positions = user.get("positions", [])
    if not positions:
        return _build_empty_portfolio_response(user)

    adapter = market_data or NullMarketDataAdapter()
    concentration_risk = _build_concentration_risk(positions)
    benchmark = _select_benchmark(user, positions)
    quote_results = adapter.fetch_quotes(positions)
    benchmark_result = adapter.fetch_benchmark(benchmark)

    live_total_value = sum(
        quote.market_value
        for quote in quote_results
        if quote.market_value is not None
    )
    total_cost_basis = sum(_position_value(position) for position in positions)
    total_gain = sum(
        (quote.market_value or 0) - _position_value(position)
        for quote, position in zip(quote_results, positions, strict=False)
    )
    portfolio_return_pct = (total_gain / total_cost_basis * 100) if total_cost_basis else None
    annualized_return_pct = None
    if portfolio_return_pct is not None:
        annualized_return_pct = portfolio_return_pct

    observations = _build_observations(
        user,
        positions,
        concentration_risk,
        benchmark,
        quote_warnings=[quote.warning for quote in quote_results if quote.warning],
        benchmark_warning=benchmark_result.warning,
    )
    alpha_pct = None
    if portfolio_return_pct is not None and benchmark_result.return_pct is not None:
        alpha_pct = round(portfolio_return_pct - benchmark_result.return_pct, 2)

    return PortfolioHealthResponse(
        concentration_risk=concentration_risk,
        performance=PerformanceSummary(
            total_return_pct=round(portfolio_return_pct, 2) if portfolio_return_pct is not None else None,
            annualized_return_pct=round(annualized_return_pct, 2) if annualized_return_pct is not None else None,
        ),
        benchmark_comparison=BenchmarkComparison(
            benchmark=benchmark,
            portfolio_return_pct=round(portfolio_return_pct, 2) if portfolio_return_pct is not None else None,
            benchmark_return_pct=benchmark_result.return_pct,
            alpha_pct=alpha_pct,
            warning=benchmark_result.warning,
        ),
        observations=observations,
        next_action=_build_next_action(positions, concentration_risk),
        disclaimer=DISCLAIMER,
        position_performance=[
            {
                "ticker": quote.ticker,
                "market_value": quote.market_value,
                "return_pct": quote.return_pct,
                "warning": quote.warning,
            }
            for quote in sorted(
                quote_results,
                key=lambda quote: quote.market_value or 0,
                reverse=True,
            )
        ],
    )
