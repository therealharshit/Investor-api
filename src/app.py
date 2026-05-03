"""FastAPI entrypoint for the Investor Copilot API service."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sse_starlette import EventSourceResponse

from src.classifier import classify
from src.market_data import YFinanceMarketDataAdapter
from src.models import ConversationTurn, QueryRequest
from src.router import dispatch
from src.safety import guard
from src.session_store import InMemorySessionStore
from src.stream_presenter import (
    event,
    fallback_preamble,
    finalize,
    success_preamble,
    to_sse_message,
)

app = FastAPI(title="Investor Copilot API")
session_store = InMemorySessionStore()
app.state.llm = None
app.state.market_data = YFinanceMarketDataAdapter()
app.state.user_loader = None


def get_llm() -> Any:
    return app.state.llm


def _default_user_loader(user_id: str) -> dict:
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures" / "users"
    for path in fixtures_dir.glob("*.json"):
        with path.open(encoding="utf-8") as handle:
            user = json.load(handle)
        if user["user_id"] == user_id:
            return user
    raise KeyError(f"Unknown user_id: {user_id}")


def get_user(user_id: str) -> dict:
    if app.state.user_loader is None:
        return _default_user_loader(user_id)
    return app.state.user_loader(user_id)


@app.post("/query/stream")
async def stream_query(payload: QueryRequest) -> EventSourceResponse:
    async def generate() -> AsyncIterator[dict[str, str]]:
        safety_verdict = guard.check(payload.query)
        if safety_verdict.blocked:
            for stream_event in finalize(
                [
                    event("meta", {"status": "started"}),
                    event("error", safety_verdict.model_dump(mode="json")),
                ]
            ):
                yield to_sse_message(stream_event)
            return

        history = session_store.get_history(payload.session_id)
        for stream_event in success_preamble()[:1]:
            yield to_sse_message(stream_event)

        classification = classify(payload.query, history, llm=get_llm())
        if classification.used_fallback:
            for stream_event in finalize(
                [
                    event("meta", {"status": "fallback"}),
                    event("thinking", {"message": "Classifying your request..."}),
                ]
                + [
                    event(
                        "response",
                        {
                            "message": (
                                "I couldn't classify that request reliably. "
                                "Please rephrase it with a bit more detail."
                            )
                        },
                    )
                ]
            ):
                yield to_sse_message(stream_event)
            return

        user = get_user(payload.user_id)
        result = dispatch(classification, user, market_data=app.state.market_data)

        session_store.append_turn(
            payload.session_id,
            ConversationTurn(role="user", content=payload.query),
        )
        session_store.append_turn(
            payload.session_id,
            ConversationTurn(role="assistant", content=result.model_dump_json()),
        )

        for stream_event in finalize(
            success_preamble()[1:]
            + [event("response", {"payload": result.model_dump(mode="json")})]
        ):
            yield to_sse_message(stream_event)

    return EventSourceResponse(generate())
