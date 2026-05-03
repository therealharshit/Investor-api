"""FastAPI entrypoint for the Investor Copilot API service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from sse_starlette import EventSourceResponse

from src.classifier import classify
from src.models import ConversationTurn, QueryRequest
from src.router import dispatch
from src.safety import guard
from src.session_store import InMemorySessionStore
from src.stream_presenter import event, fallback_preamble, finalize, success_preamble

app = FastAPI(title="Investor Copilot API")
session_store = InMemorySessionStore()


def get_llm() -> Any:
    raise NotImplementedError("Inject the OpenAI client during implementation.")


def get_user(user_id: str) -> dict:
    raise NotImplementedError(f"Load user profile for {user_id}.")


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
                yield stream_event.model_dump(mode="json")
            return

        history = session_store.get_history(payload.session_id)
        for stream_event in success_preamble()[:1]:
            yield stream_event.model_dump(mode="json")

        classification = classify(payload.query, history, llm=get_llm())
        if classification.used_fallback:
            for stream_event in finalize(
                fallback_preamble()
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
                yield stream_event.model_dump(mode="json")
            return

        user = get_user(payload.user_id)
        result = dispatch(classification, user)

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
            yield stream_event.model_dump(mode="json")

    return EventSourceResponse(generate())
