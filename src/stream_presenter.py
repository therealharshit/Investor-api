"""Shared SSE event formatting.

Stream order
------------
success:
  meta -> thinking* -> response* -> done

fallback:
  meta -> thinking -> error/response -> done

stub:
  meta -> thinking -> response -> done
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from src.models import StreamEvent


def event(
    event_type: Literal["meta", "thinking", "response", "error", "done"],
    data: dict,
) -> StreamEvent:
    return StreamEvent(event=event_type, data=data)


def success_preamble() -> list[StreamEvent]:
    return [
        event("meta", {"status": "started"}),
        event("thinking", {"message": "Analyzing your holdings..."}),
        event("thinking", {"message": "Comparing to your benchmark..."}),
        event("thinking", {"message": "Flagging what matters most..."}),
    ]


def fallback_preamble() -> list[StreamEvent]:
    return [
        event("meta", {"status": "started"}),
        event("thinking", {"message": "Classifying your request..."}),
    ]


def finalize(events: Iterable[StreamEvent]) -> list[StreamEvent]:
    materialized = list(events)
    materialized.append(event("done", {"status": "complete"}))
    return materialized
