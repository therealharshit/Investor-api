"""LLM-backed intent classification with deterministic fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import ValidationError

from src.models import (
    AgentName,
    ClassificationResult,
    ClassifierEntities,
    ConversationTurn,
    InformationalSafetyVerdict,
)

TICKER_ALIASES = {
    "aapl": "AAPL",
    "apple": "AAPL",
    "amd": "AMD",
    "asml": "ASML",
    "asml.as": "ASML.AS",
    "barclays": "BARC.L",
    "barc.l": "BARC.L",
    "ftse": "FTSE 100",
    "gold": "GOLD",
    "hsbc": "HSBA.L",
    "hsba.l": "HSBA.L",
    "jnj": "JNJ",
    "ko": "KO",
    "microsoft": "MSFT",
    "microsfot": "MSFT",
    "msft": "MSFT",
    "nikkei": "NIKKEI 225",
    "nvidia": "NVDA",
    "nvda": "NVDA",
    "pg": "PG",
    "s&p 500": "S&P 500",
    "sp500": "S&P 500",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "voo": "VOO",
    "vti": "VTI",
    "vxus": "VXUS",
}

CURRENCY_CODES = {"usd": "USD", "eur": "EUR", "gbp": "GBP", "jpy": "JPY"}

SYSTEM_PROMPT = """You are a financial-intent classifier for a novice-investor assistant.
Return one JSON object with exactly these top-level keys:
intent, agent, entities, informational_safety_verdict.

Rules:
- agent must be one of: customer_support, financial_calculator, financial_planning, general_query, investment_strategy, market_research, portfolio_health, predictive_analysis, product_recommendation, risk_assessment
- intent should be a short lowercase label
- entities may include: action, amount, currency, frequency, goal, horizon, index, intent, period_years, rate, sectors, tickers, time_period, topics
- informational_safety_verdict should be an object with safe (boolean), category (string|null), rationale (string|null)
- resolve follow-ups using the provided prior conversation
- do not invent entities that are not supported by the user text or context
- keep the JSON valid and do not wrap it in markdown
"""


def _normalize_history(history: list[ConversationTurn] | list[str]) -> list[str]:
    normalized: list[str] = []
    for item in history:
        if isinstance(item, ConversationTurn):
            normalized.append(item.content)
        else:
            normalized.append(item)
    return normalized


def _extract_tickers(text: str, history_text: list[str]) -> list[str]:
    tickers: list[str] = []
    combined = [text, *history_text]
    for source in combined:
        lowered = source.lower()
        for alias, resolved in TICKER_ALIASES.items():
            if alias in lowered and "." not in resolved and " " not in resolved:
                if resolved not in tickers:
                    tickers.append(resolved)
        for match in re.findall(r"\b[A-Z]{2,5}(?:\.[A-Z]{1,3})?\b", source):
            resolved = TICKER_ALIASES.get(match.lower(), match.upper())
            if resolved not in tickers and resolved not in {"USD", "EUR", "GBP", "JPY"}:
                tickers.append(resolved)

    if "compare them" in text.lower():
        history_tickers: list[str] = []
        for source in history_text:
            for alias, resolved in TICKER_ALIASES.items():
                if alias in source.lower() and "." not in resolved and " " not in resolved:
                    if resolved not in history_tickers:
                        history_tickers.append(resolved)
        if history_tickers:
            tickers = history_tickers[-2:]

    return tickers


def _extract_topics(text: str) -> list[str]:
    topic_map = {
        "bank account": "bank account",
        "beta": "beta",
        "capital gains": "LTCG",
        "compound interest": "compound interest",
        "dollar cost averaging": "DCA",
        "drawdown": "max drawdown",
        "emerging market": "emerging markets",
        "etf": "ETF",
        "fx": "FX",
        "index fund": "index fund",
        "large cap": "large cap",
        "login": "login",
        "lump-sum": "lump-sum",
        "ltcg": "LTCG",
        "mutual fund": "mutual fund",
        "p/e": "P/E ratio",
        "recurring investment": "recurring investment",
        "recession": "recession",
        "transaction history": "transaction history",
        "world": "world",
        "dividend": "dividend",
    }
    lowered = text.lower()
    topics = [value for key, value in topic_map.items() if key in lowered]
    return list(dict.fromkeys(topics))


def _extract_amount(text: str) -> float | None:
    lowered = text.lower().replace(",", "")
    contextual_patterns = (
        r"(?:invest|investing|loan|profit|fund of|convert)\s+(\d+(?:\.\d+)?)\s*(k)?",
        r"(\d+(?:\.\d+)?)\s*(k)?\s*(?:usd|eur|gbp|jpy)\b",
        r"(\d+(?:\.\d+)?)\s*(k)?\s*(?:monthly|weekly|daily|yearly)\b",
    )
    match = None
    for pattern in contextual_patterns:
        match = re.search(pattern, lowered)
        if match:
            break
    if not match:
        if re.fullmatch(r"\d+(?:\.\d+)?\s*(k)?", lowered.strip()):
            match = re.search(r"\b(\d+(?:\.\d+)?)\s*(k)?\b", lowered)
        else:
            return None
    if not match:
        return None
    amount = float(match.group(1))
    if match.group(2):
        amount *= 1000
    return amount


def _extract_rate(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text.lower())
    if not match:
        return None
    return float(match.group(1)) / 100


def _extract_period_years(text: str) -> int | None:
    match = re.search(r"(\d+)\s*years?", text.lower())
    if not match:
        return None
    return int(match.group(1))


def _extract_horizon(text: str) -> str | None:
    lowered = text.lower()
    if "6 months" in lowered:
        return "6_months"
    if "5 years" in lowered:
        return "5_years"
    if "1 year" in lowered:
        return "1_year"
    return None


def _extract_frequency(text: str) -> str | None:
    lowered = text.lower()
    if "monthly" in lowered or "a month" in lowered:
        return "monthly"
    if "weekly" in lowered:
        return "weekly"
    if "daily" in lowered:
        return "daily"
    if "yearly" in lowered or "annually" in lowered:
        return "yearly"
    return None


def _extract_currency(text: str) -> str | None:
    lowered = text.lower()
    for key, value in CURRENCY_CODES.items():
        if key in lowered:
            return value
    return None


def _extract_goal(text: str) -> str | None:
    lowered = text.lower()
    if "retire" in lowered or "retirement" in lowered:
        return "retirement"
    if "college" in lowered or "education" in lowered:
        return "education"
    if "house" in lowered:
        return "house"
    if "fire" in lowered:
        return "FIRE"
    return None


def _extract_index(text: str) -> str | None:
    lowered = text.lower()
    if "s&p 500" in lowered or "sp500" in lowered:
        return "S&P 500"
    if "ftse" in lowered:
        return "FTSE 100"
    if "nikkei" in lowered:
        return "NIKKEI 225"
    if "msci world" in lowered:
        return "MSCI World"
    return None


def _extract_time_period(text: str) -> str | None:
    lowered = text.lower()
    if "today" in lowered:
        return "today"
    if "this week" in lowered:
        return "this_week"
    if "this month" in lowered:
        return "this_month"
    return None


def _extract_action(text: str) -> str | None:
    lowered = text.lower()
    if "rebalance" in lowered:
        return "rebalance"
    if "hedge" in lowered:
        return "hedge"
    if "sell" in lowered:
        return "sell"
    if "buy" in lowered:
        return "buy"
    return None


def _extract_sectors(text: str) -> list[str]:
    lowered = text.lower()
    sectors = []
    if "tech" in lowered or "technology" in lowered:
        sectors.append("technology")
    return sectors


def _infer_agent(text: str, history: list[str], tickers: list[str]) -> tuple[AgentName, str]:
    lowered = text.lower().strip()

    if lowered in {"hi", "hello", "thanks", "thx"}:
        return AgentName.GENERAL_QUERY, "general_query"
    if "can't login" in lowered or "linked bank account" in lowered or "transaction history" in lowered or "recurring investment" in lowered:
        return AgentName.CUSTOMER_SUPPORT, "customer_support"
    if "predict" in lowered or "where will" in lowered:
        return AgentName.PREDICTIVE_ANALYSIS, "predictive_analysis"
    if (
        "stress test" in lowered
        or "beta" in lowered
        or "max drawdown" in lowered
        or "downside risk" in lowered
        or "weakening" in lowered
        or "exposed" in lowered
    ):
        return AgentName.RISK_ASSESSMENT, "risk_assessment"
    if "recommend" in lowered or "best low-cost" in lowered or "which fund" in lowered:
        return AgentName.PRODUCT_RECOMMENDATION, "product_recommendation"
    if "retire" in lowered or "college fund" in lowered or "down payment" in lowered or "fire plan" in lowered or "save for retirement" in lowered:
        return AgentName.FINANCIAL_PLANNING, "financial_planning"
    if (
        "calculate" in lowered
        or "future value" in lowered
        or "mortgage payment" in lowered
        or "convert " in lowered
        or "capital gains tax" in lowered
        or (re.search(r"\b\d", lowered) and ("monthly" in lowered or "years" in lowered))
    ):
        return AgentName.FINANCIAL_CALCULATOR, "financial_calculator"
    if "how is my portfolio doing" in lowered or "health check" in lowered or "diversified" in lowered or "concentration risk" in lowered or "beating the market" in lowered or "review my holdings" in lowered or "portfolio summary" in lowered:
        return AgentName.PORTFOLIO_HEALTH, "portfolio_health"
    if "what's my concentration risk" in lowered:
        return AgentName.PORTFOLIO_HEALTH, "portfolio_health"
    if "what should i sell" in lowered and "portfolio" in lowered:
        return AgentName.PORTFOLIO_HEALTH, "portfolio_health"
    if "should i " in lowered or lowered.startswith("rebalance ") or "good time to invest" in lowered or "hedge my" in lowered:
        return AgentName.INVESTMENT_STRATEGY, "investment_strategy"
    if "what is" in lowered or "explain" in lowered or "difference between" in lowered or "what does" in lowered:
        return AgentName.GENERAL_QUERY, "general_query"
    if tickers and (lowered == tickers[0].lower() or "news" in lowered or "price" in lowered or "tell me about" in lowered or "how is " in lowered or "what's happening" in lowered or "compare" in lowered):
        return AgentName.MARKET_RESEARCH, "market_research"
    if "markets today" in lowered or "ftse" in lowered or "nikkei" in lowered or "eur/usd" in lowered or "gold price" in lowered:
        return AgentName.MARKET_RESEARCH, "market_research"
    if lowered.startswith("how much do i own") and history:
        return AgentName.PORTFOLIO_HEALTH, "portfolio_query"
    if lowered.startswith("should i sell some") and history:
        return AgentName.INVESTMENT_STRATEGY, "investment_strategy"
    if lowered.startswith("what about ") and history:
        return AgentName.MARKET_RESEARCH, "market_research"
    if lowered == "compare them":
        return AgentName.MARKET_RESEARCH, "market_research"
    return AgentName.GENERAL_QUERY, "general_query"


def _heuristic_classification(query: str, history: list[ConversationTurn] | list[str]) -> ClassificationResult:
    history_text = _normalize_history(history)
    tickers = _extract_tickers(query, history_text)
    topics = _extract_topics(query)
    action = _extract_action(query)
    amount = _extract_amount(query)
    currency = _extract_currency(query)
    frequency = _extract_frequency(query)
    goal = _extract_goal(query)
    horizon = _extract_horizon(query)
    index = _extract_index(query)
    period_years = _extract_period_years(query)
    rate = _extract_rate(query)
    sectors = _extract_sectors(query)
    time_period = _extract_time_period(query)

    agent, intent = _infer_agent(query, history_text, tickers)
    entities = ClassifierEntities(
        action=action,
        amount=amount,
        currency=currency,
        frequency=frequency,
        goal=goal,
        horizon=horizon,
        index=index,
        intent="comparison" if query.lower().strip() == "compare them" else None,
        period_years=period_years,
        rate=rate,
        sectors=sectors,
        tickers=tickers,
        time_period=time_period,
        topics=topics,
    )

    if "portfolio" in query.lower() and "sell" in query.lower() and not entities.action:
        entities.action = "sell"

    return ClassificationResult(
        intent=intent,
        agent=agent,
        entities=entities,
        informational_safety_verdict=InformationalSafetyVerdict(safe=True),
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


def _conversation_payload(history: list[ConversationTurn] | list[str]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for item in history:
        if isinstance(item, ConversationTurn):
            payload.append({"role": item.role, "content": item.content})
        else:
            payload.append({"role": "user", "content": item})
    return payload


def _llm_classifier_call(
    provider: str,
    query: str,
    history: list[ConversationTurn] | list[str],
    client: Any,
    model: str,
) -> dict[str, Any]:
    if provider == "gemini":
        from google.genai import types

        contents = []
        for item in history:
            if isinstance(item, ConversationTurn):
                role = "model" if item.role == "assistant" else "user"
                content_text = item.content
            else:
                role = "user"
                content_text = item
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content_text)]
                )
            )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=query)]
            )
        )
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.0,
        )
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        content = response.text or "{}"
        return json.loads(content)

    elif provider == "openai":
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *(_conversation_payload(history)),
            {"role": "user", "content": query},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    raise ValueError(f"Unknown LLM provider: {provider}")


def build_llm_classifier() -> Any | None:
    """Return a callable classifier backed by the configured LLM provider."""
    # Check Gemini configuration first
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        try:
            from google import genai
        except ImportError:  # pragma: no cover
            return None

        client = genai.Client(api_key=gemini_key)
        return lambda query, history=None: _llm_classifier_call("gemini", query, history or [], client, model)

    # Fallback to OpenAI configuration
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            from openai import OpenAI
        except ImportError:  # pragma: no cover
            return None

        client = OpenAI(api_key=openai_key)
        return lambda query, history=None: _llm_classifier_call("openai", query, history or [], client, model)

    return None


def classify(
    query: str,
    history: list[ConversationTurn] | list[str] | None = None,
    llm: Any | None = None,
) -> ClassificationResult:
    """Classify the current user query plus bounded prior context."""

    history = history or []
    heuristic = _heuristic_classification(query, history)
    if llm is None:
        return heuristic

    try:
        try:
            raw = llm(query, history)
        except TypeError:
            raw = llm(query)
    except Exception:
        return heuristic

    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
        return ClassificationResult.model_validate(raw)
    except (ValidationError, json.JSONDecodeError, TypeError):
        return _fallback_classification(query)
