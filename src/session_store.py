"""Conversation memory for follow-up classifier context."""

from __future__ import annotations

from collections import defaultdict

from src.models import ConversationTurn


class InMemorySessionStore:
    """Stores a bounded turn window per session for follow-up resolution."""

    def __init__(self, max_user_turns: int = 3) -> None:
        self.max_user_turns = max_user_turns
        self._sessions: dict[str, list[ConversationTurn]] = defaultdict(list)

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        return list(self._sessions.get(session_id, []))

    def append_turn(self, session_id: str, turn: ConversationTurn) -> None:
        history = self._sessions[session_id]
        history.append(turn)
        self._sessions[session_id] = self._trim_history(history)

    def _trim_history(self, history: list[ConversationTurn]) -> list[ConversationTurn]:
        user_turns_seen = 0
        kept: list[ConversationTurn] = []
        for turn in reversed(history):
            kept.append(turn)
            if turn.role == "user":
                user_turns_seen += 1
            if user_turns_seen >= self.max_user_turns:
                break
        kept.reverse()
        return kept
