"""
Skeleton test for the Portfolio Health agent.

Wire your agent import and remove the skip decorators.
"""
from src.agents.portfolio_health import run
from src.market_data import BenchmarkResult, QuoteResult


class FakeMarketData:
    def fetch_quotes(self, positions):
        return [
            QuoteResult(
                ticker=position["ticker"],
                current_price=position["avg_cost"] * 1.1,
                return_pct=10.0,
                market_value=round(position["quantity"] * position["avg_cost"] * 1.1, 2),
                warning=None,
            )
            for position in positions
        ]

    def fetch_benchmark(self, benchmark):
        return BenchmarkResult(benchmark=benchmark, return_pct=7.5)


class DegradedMarketData:
    def fetch_quotes(self, positions):
        return [
            QuoteResult(
                ticker=position["ticker"],
                market_value=round(position["quantity"] * position["avg_cost"], 2),
                warning="provider unavailable",
            )
            for position in positions
        ]

    def fetch_benchmark(self, benchmark):
        return BenchmarkResult(benchmark=benchmark, warning="provider unavailable")


def test_portfolio_health_does_not_crash_on_empty_portfolio(load_user, mock_llm):
    """
    user_004 has no positions. Agent must not crash.
    """
    user = load_user("usr_004")
    response = run(user, market_data=FakeMarketData(), llm=mock_llm)

    assert response is not None
    assert response.disclaimer
    assert response.next_action.label
    assert "no positions" in response.observations[0].text.lower()


def test_portfolio_health_flags_concentration(load_user, mock_llm):
    """
    user_003 has ~60% in NVDA. Agent must surface this.
    """
    user = load_user("usr_003")
    response = run(user, market_data=FakeMarketData(), llm=mock_llm)

    assert response.concentration_risk.flag in {"high", "warning"}
    assert response.performance.total_return_pct is not None


def test_portfolio_health_includes_disclaimer(load_user, mock_llm):
    user = load_user("usr_001")
    response = run(user, market_data=FakeMarketData(), llm=mock_llm)
    assert response.disclaimer
    assert "not investment advice" in response.disclaimer.lower()


def test_portfolio_health_uses_global_fallback_for_multi_market_user(load_user, mock_llm):
    user = load_user("usr_006")
    response = run(user, market_data=FakeMarketData(), llm=mock_llm)

    assert response.benchmark_comparison is not None
    assert response.benchmark_comparison.benchmark == "NIKKEI 225"


def test_portfolio_health_degrades_cleanly_when_market_data_is_missing(load_user, mock_llm):
    user = load_user("usr_001")
    response = run(user, market_data=DegradedMarketData(), llm=mock_llm)

    assert response.benchmark_comparison is not None
    assert response.benchmark_comparison.warning
    assert any("degraded estimates" in observation.text.lower() for observation in response.observations)
