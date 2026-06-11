import os

import pytest

from core.conversation import build_conversation_prompt
from core.gemini_client import GeminiAPIKeyClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set",
)


def test_gemini_live_streaming():
    client = GeminiAPIKeyClient(
        api_key=os.environ["GEMINI_API_KEY"],
        model="gemini-2.5-flash",
    )
    chunks = list(client.generate("Reply with exactly: pong"))
    text = "".join(chunks).lower()
    assert text


def test_gemini_conversation_memory_prompt():
    history = [
        {"role": "user", "content": "Hello, who are you?"},
        {"role": "assistant", "content": "I am Virtuoso, a coding assistant."},
    ]
    prompt = build_conversation_prompt("What did I just ask you?", history)
    client = GeminiAPIKeyClient(
        api_key=os.environ["GEMINI_API_KEY"],
        model="gemini-2.5-flash",
    )
    chunks = list(client.generate(prompt))
    text = "".join(chunks).lower()
    assert "hello" in text or "who are you" in text
