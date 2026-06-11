import types
from unittest.mock import MagicMock, patch

from core.gemini_client import GeminiAPIKeyClient


class DummyChunk:
    def __init__(self, text: str):
        self.text = text


def test_gemini_api_key_client_streams_chunks():
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [
        DummyChunk("Hello"),
        DummyChunk(" world"),
    ]

    with patch("core.gemini_client.genai") as mock_genai, patch("core.gemini_client.genai_types") as mock_types:
        mock_genai.Client.return_value = mock_client
        mock_types.GenerateContentConfig.return_value = object()

        client = GeminiAPIKeyClient(api_key="test-key", model="gemini-2.5-flash")
        chunks = list(client.generate("Hi", system_prompt="Be brief"))
        assert chunks == ["Hello", " world"]
        mock_client.models.generate_content_stream.assert_called_once()
