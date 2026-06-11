from core.conversation import build_conversation_prompt, max_conversation_exchanges


def test_build_conversation_prompt_without_history():
    assert build_conversation_prompt("Hello", []) == "Hello"


def test_build_conversation_prompt_with_history():
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    prompt = build_conversation_prompt("What did I say?", history)
    assert "Previous conversation:" in prompt
    assert "User: Hi" in prompt
    assert "Assistant: Hello!" in prompt
    assert "Current query: What did I say?" in prompt


def test_build_conversation_prompt_limits_exchanges():
    history = []
    for i in range(12):
        history.append({"role": "user", "content": f"u{i}"})
        history.append({"role": "assistant", "content": f"a{i}"})
    prompt = build_conversation_prompt("latest", history, max_exchanges=2)
    assert "u10" in prompt
    assert "a10" in prompt
    assert "u0" not in prompt


def test_max_conversation_exchanges_from_config():
    assert max_conversation_exchanges({"cli": {"max_conversation_exchanges": 5}}) == 5
    assert max_conversation_exchanges({}) == 10
