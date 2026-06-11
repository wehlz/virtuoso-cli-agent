from core import config as config_module
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


def test_load_config_creates_default_when_missing(tmp_path, monkeypatch):
    cfg_path = tmp_path / "virtuoso.yaml"
    monkeypatch.setattr(config_module, "_config_path", lambda: cfg_path)

    loaded = config_module.load_config()

    assert cfg_path.exists()
    assert loaded["llm"]["backend"] == "gemini-apikey"
    assert loaded["llm"]["gemini"]["model"] == "gemini-2.5-flash"
