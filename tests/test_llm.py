import pytest
from unittest.mock import patch, MagicMock
from ses.core.llm import LocalLLMProvider

def test_local_llm_provider_initialization():
    provider = LocalLLMProvider(model_override="test-llama")
    assert provider.model == "test-llama"

def test_generate_answer_no_context():
    provider = LocalLLMProvider()
    response = provider.generate_answer("query", [])
    assert "no contiene información suficiente" in response

@patch("ses.core.llm.urllib.request.urlopen")
def test_generate_answer_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "Respuesta mockeada"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    provider = LocalLLMProvider()
    docs = [{"text": "Contexto de prueba", "metadata": {"file_name": "test.txt"}}]
    
    response = provider.generate_answer("¿Qué es esto?", docs)
    assert response == "Respuesta mockeada"
