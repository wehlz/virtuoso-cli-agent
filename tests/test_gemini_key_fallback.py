import yaml

from core.gemini_setup import get_gemini_api_key


def test_get_gemini_api_key_from_dist_fallback(tmp_path, monkeypatch):
    root_cfg = tmp_path / "virtuoso.yaml"
    root_cfg.write_text("llm:\n  gemini:\n    api_key: ''\n", encoding="utf-8")
    dist_cfg = tmp_path / "dist" / "virtuoso.yaml"
    dist_cfg.parent.mkdir()
    dist_cfg.write_text(
        yaml.safe_dump({"llm": {"gemini": {"api_key": "dist-test-key-12345"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("core.paths.app_dir", lambda: tmp_path)
    assert get_gemini_api_key(yaml.safe_load(root_cfg.read_text())) == "dist-test-key-12345"
