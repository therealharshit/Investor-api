from src.models import ConversationTurn
from src.session_store import InMemorySessionStore


def test_session_store_keeps_bounded_user_turn_window():
    store = InMemorySessionStore(max_user_turns=2)

    store.append_turn("abc", ConversationTurn(role="user", content="one"))
    store.append_turn("abc", ConversationTurn(role="assistant", content="a1"))
    store.append_turn("abc", ConversationTurn(role="user", content="two"))
    store.append_turn("abc", ConversationTurn(role="assistant", content="a2"))
    store.append_turn("abc", ConversationTurn(role="user", content="three"))

    history = store.get_history("abc")

    assert [turn.content for turn in history] == ["two", "a2", "three"]


def test_session_store_returns_empty_history_for_new_session():
    store = InMemorySessionStore()

    assert store.get_history("missing") == []
