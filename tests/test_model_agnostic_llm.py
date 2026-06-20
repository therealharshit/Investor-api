import os
from unittest.mock import MagicMock, patch
import pytest
from src.classifier import build_llm_classifier
from src.models import ConversationTurn


def test_build_llm_classifier_neither_set(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    classifier = build_llm_classifier()
    assert classifier is None


def test_build_llm_classifier_gemini_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    mock_client_instance = MagicMock()
    with patch("google.genai.Client", return_value=mock_client_instance) as mock_client_cls:
        classifier = build_llm_classifier()
        assert classifier is not None
        mock_client_cls.assert_called_once_with(api_key="mock-gemini-key")
        
        mock_response = MagicMock()
        mock_response.text = '{"intent": "test_intent", "agent": "general_query"}'
        mock_client_instance.models.generate_content.return_value = mock_response
        
        res = classifier("hello", history=[ConversationTurn(role="user", content="hi")])
        assert res == {"intent": "test_intent", "agent": "general_query"}
        
        mock_client_instance.models.generate_content.assert_called_once()
        _, kwargs = mock_client_instance.models.generate_content.call_args
        assert kwargs["model"] == "gemini-test-model"
        assert len(kwargs["contents"]) == 2


def test_build_llm_classifier_openai_set(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "openai-test-model")
    
    mock_client_instance = MagicMock()
    with patch("openai.OpenAI", return_value=mock_client_instance) as mock_client_cls:
        classifier = build_llm_classifier()
        assert classifier is not None
        mock_client_cls.assert_called_once_with(api_key="mock-openai-key")
        
        mock_choice = MagicMock()
        mock_choice.message.content = '{"intent": "test_intent", "agent": "general_query"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        res = classifier("hello")
        assert res == {"intent": "test_intent", "agent": "general_query"}
        
        mock_client_instance.chat.completions.create.assert_called_once()
        _, kwargs = mock_client_instance.chat.completions.create.call_args
        assert kwargs["model"] == "openai-test-model"
        assert kwargs["response_format"] == {"type": "json_object"}
