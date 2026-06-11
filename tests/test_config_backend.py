from core.config import resolve_backend


def test_resolve_backend_defaults_to_gemini():
    cfg = {"llm": {"backend": "auto", "gemini": {"api_key": ""}}}
    assert resolve_backend(cfg) == "gemini-apikey"


def test_resolve_backend_prefers_gemini_when_key_present():
    cfg = {
        "llm": {"backend": "auto", "gemini": {"api_key": "abc123"}},
    }
    assert resolve_backend(cfg) == "gemini-apikey"


def test_resolve_backend_honors_explicit_shimmy():
    cfg = {"llm": {"backend": "shimmy", "gemini": {"api_key": "abc123"}}}
    assert resolve_backend(cfg) == "shimmy"


def test_resolve_backend_migrates_legacy_qwen():
    cfg = {"llm": {"backend": "qwen"}}
    assert resolve_backend(cfg) == "gemini-apikey"
