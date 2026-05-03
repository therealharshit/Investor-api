"""
Skeleton test for the Portfolio Health agent.

Wire your agent import and remove the skip decorators.
"""
from src.agents.portfolio_health import run


def test_portfolio_health_does_not_crash_on_empty_portfolio(load_user, mock_llm):
    """
    user_004 has no positions. Agent must not crash.
    """
    user = load_user("usr_004")
    response = run(user, llm=mock_llm)

    assert response is not None
    assert response.disclaimer
    assert response.next_action.label
    assert "no positions" in response.observations[0].text.lower()


def test_portfolio_health_flags_concentration(load_user, mock_llm):
    """
    user_003 has ~60% in NVDA. Agent must surface this.
    """
    user = load_user("usr_003")
    response = run(user, llm=mock_llm)

    assert response.concentration_risk.flag in {"high", "warning", "moderate"}


def test_portfolio_health_includes_disclaimer(load_user, mock_llm):
    user = load_user("usr_001")
    response = run(user, llm=mock_llm)
    assert response.disclaimer
    assert "not investment advice" in response.disclaimer.lower()
