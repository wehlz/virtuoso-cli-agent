import json
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock

from core.ide_server import IdeServerState, make_handler, parse_chat_messages


def test_parse_chat_messages_extracts_user_and_system():
    prompt, system = parse_chat_messages(
        [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Hello"},
        ]
    )
    assert prompt == "Hello"
    assert system == "Be concise"


def test_ide_server_chat_completion():
    state = IdeServerState()
    state.model_id = "test-model"
    mock_client = MagicMock()
    mock_client.generate.return_value = iter(["Hi", " there"])
    state.llm_client = mock_client

    handler = make_handler(state)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        import requests

        response = requests.post(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
            },
            timeout=5,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["choices"][0]["message"]["content"] == "Hi there"
    finally:
        httpd.shutdown()
