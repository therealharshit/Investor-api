import json

from fastapi.testclient import TestClient

from src.app import app, session_store
from src.models import AgentName


def _read_sse(response) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current_event = None
    current_data = None
    for raw_line in response.iter_lines():
        if not raw_line:
            if current_event is not None and current_data is not None:
                events.append((current_event, json.loads(current_data)))
            current_event = None
            current_data = None
            continue
        if raw_line.startswith("event: "):
            current_event = raw_line.split("event: ", 1)[1]
        elif raw_line.startswith("data: "):
            current_data = raw_line.split("data: ", 1)[1]
    return events


def test_streaming_endpoint_emits_classifier_fallback_sequence(monkeypatch):
    session_store._sessions.clear()
    app.state.llm = lambda query: {"malformed": query}
    app.state.user_loader = lambda user_id: {"user_id": user_id, "positions": []}

    client = TestClient(app)
    response = client.post(
        "/query/stream",
        json={"session_id": "sess-1", "user_id": "usr_004", "query": "how am i doing?"},
    )

    assert response.status_code == 200
    events = _read_sse(response)
    assert [event for event, _ in events] == ["meta", "meta", "thinking", "response", "done"]
    assert "couldn't classify" in events[-2][1]["message"].lower()


def test_streaming_endpoint_emits_stub_route_sequence(monkeypatch):
    session_store._sessions.clear()
    app.state.llm = lambda query: {
        "intent": "market_research",
        "agent": AgentName.MARKET_RESEARCH.value,
        "entities": {"tickers": ["NVDA"]},
        "informational_safety_verdict": {"safe": True},
    }
    app.state.user_loader = lambda user_id: {"user_id": user_id, "positions": []}

    client = TestClient(app)
    response = client.post(
        "/query/stream",
        json={"session_id": "sess-2", "user_id": "usr_004", "query": "tell me about nvidia"},
    )

    assert response.status_code == 200
    events = _read_sse(response)
    assert [event for event, _ in events] == [
        "meta",
        "thinking",
        "thinking",
        "thinking",
        "response",
        "done",
    ]
    assert "not implemented" in events[-2][1]["payload"]["message"].lower()
